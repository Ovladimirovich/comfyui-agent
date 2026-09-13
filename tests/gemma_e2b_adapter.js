/**
 * Gemma E2B ↔ comfyui-mcp Adapter
 * 
 * Связывает Gemma E2B (llama.cpp) с ComfyUI через MCP protocol.
 * 
 * Поток:
 * 1. Запрос к Gemma E2B с tool definitions
 * 2. Gemma возвращает tool_calls
 * 3. Выполнение tool_calls через comfyui-mcp
 * 4. Отправка результатов обратно в Gemma E2B
 * 5. Повтор до финального ответа
 */

const http = require('http');
const { spawn } = require('child_process');
const readline = require('readline');

// Конфигурация
const LLAMA_URL = process.env.LLAMA_URL || 'http://127.0.0.1:8082';
const COMFYUI_URL = process.env.COMFYUI_URL || 'http://127.0.0.1:8188';
const MAX_TOOL_ROUNDS = parseInt(process.env.MAX_TOOL_ROUNDS || '10');
const MODEL = process.env.MODEL || 'default';

// MCP Server path
const MCP_SERVER = 'C:\\Users\\1\\AppData\\Roaming\\npm\\node_modules\\comfyui-mcp\\dist\\index.js';

class McpClient {
  constructor() {
    this.server = null;
    this.requestId = 0;
    this.pending = new Map();
    this.tools = [];
    this.buffer = '';
  }

  async connect() {
    return new Promise((resolve, reject) => {
      const env = {
        ...process.env,
        COMFYUI_URL: COMFYUI_URL,
        COMFYUI_MCP_TOOL_MODE: 'full'
      };

      this.server = spawn('node', [MCP_SERVER], {
        env,
        stdio: ['pipe', 'pipe', 'pipe']
      });

      this.server.stdout.on('data', (data) => {
        this.buffer += data.toString();
        this.processBuffer();
      });

      this.server.stderr.on('data', (data) => {
        // Игнорируем stderr от MCP
      });

      this.server.on('error', reject);

      // Инициализация MCP
      this.sendRequest('initialize', {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: { name: 'gemma-e2b-adapter', version: '1.0.0' }
      }).then(() => {
        // Отправляем notification (не требует ответа)
        const msg = { jsonrpc: '2.0', method: 'notifications/initialized', params: {} };
        this.server.stdin.write(JSON.stringify(msg) + '\n');
        return this.listTools();
      }).then((tools) => {
        this.tools = tools;
        resolve(tools);
      }).catch(reject);
    });
  }

  processBuffer() {
    const lines = this.buffer.split('\n');
    this.buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg = JSON.parse(line);
        
        // Логируем для отладки
        if (process.env.DEBUG) {
          console.error('MCP:', JSON.stringify(msg).substring(0, 200));
        }
        
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) {
            reject(new Error(msg.error.message));
          } else {
            resolve(msg.result);
          }
        }
      } catch (e) {
        if (process.env.DEBUG) {
          console.error('MCP parse error:', line.substring(0, 100));
        }
      }
    }
  }

  sendRequest(method, params) {
    return new Promise((resolve, reject) => {
      const id = ++this.requestId;
      const msg = { jsonrpc: '2.0', id, method, params };
      this.pending.set(id, { resolve, reject });
      this.server.stdin.write(JSON.stringify(msg) + '\n');

      // Таймаут 30 сек
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`Timeout waiting for response to ${method}`));
        }
      }, 30000);
    });
  }

  async listTools() {
    const result = await this.sendRequest('tools/list', {});
    return result.tools || [];
  }

  async callTool(name, args) {
    const result = await this.sendRequest('tools/call', { name, arguments: args });
    return result;
  }

  disconnect() {
    if (this.server) {
      this.server.kill();
    }
  }
}

async function llamaRequest(messages, tools = []) {
  const body = {
    model: MODEL,
    messages,
    max_tokens: 1024
  };

  if (tools.length > 0) {
    // Упрощаем tools для совместимости с llama.cpp
    body.tools = tools.map(t => {
      const params = t.inputSchema || { type: 'object', properties: {} };
      
      // Упрощаем schema — убираем complex nesting
      const simplify = (obj) => {
        if (!obj || typeof obj !== 'object') return obj;
        if (obj.type === 'object' && obj.properties) {
          const simple = {};
          for (const [k, v] of Object.entries(obj.properties)) {
            if (v.type === 'object' && v.properties) {
              simple[k] = { type: 'object', description: v.description || '' };
            } else {
              simple[k] = { type: v.type || 'string', description: v.description || '' };
            }
          }
          return { type: 'object', properties: simple };
        }
        return obj;
      };
      
      return {
        type: 'function',
        function: {
          name: t.name,
          description: (t.description || '').substring(0, 200),
          parameters: simplify(params)
        }
      };
    });
    
    // Ограничиваем количество tools для small model
    body.tools = body.tools.slice(0, 15);
  }

  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const url = new URL(`${LLAMA_URL}/v1/chat/completions`);

    const req = http.request({
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data)
      },
      timeout: 300000 // 5 минут на CPU
    }, (res) => {
      let responseData = '';
      res.on('data', chunk => responseData += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(responseData));
        } catch (e) {
          reject(new Error(`Failed to parse response: ${responseData}`));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });

    req.write(data);
    req.end();
  });
}

async function runAgent(userPrompt, mcp) {
  const messages = [
    {
      role: 'system',
      content: `You are a ComfyUI expert operator. You have access to MCP tools that control ComfyUI.
When the user asks you to generate images, edit images, create workflows, or manage ComfyUI:
1. Use the appropriate MCP tools to fulfill the request
2. Build workflows node by node using the available tools
3. Execute workflows and return results
4. If an error occurs, diagnose and fix it

Always use the tools. Do not describe what you would do - actually do it using the tools.`
    },
    { role: 'user', content: userPrompt }
  ];

  console.log(`\n${'='.repeat(60)}`);
  console.log(`USER: ${userPrompt}`);
  console.log(`${'='.repeat(60)}`);

  for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
    console.log(`\n--- Round ${round + 1} ---`);
    console.log('Sending to Gemma E2B...');

    const response = await llamaRequest(messages, mcp.tools);
    console.log('Raw response:', JSON.stringify(response).substring(0, 500));
    
    if (!response.choices) {
      console.log('ERROR: No choices in response');
      break;
    }
    
    const choice = response.choices[0];

    if (!choice) {
      console.log('ERROR: No choice in response');
      break;
    }

    const message = choice.message;
    console.log(`Finish reason: ${choice.finish_reason}`);
    console.log(`Content: ${(message.content || '').substring(0, 200)}`);

    // Если нет tool_calls — финальный ответ
    if (choice.finish_reason !== 'tool_calls' || !message.tool_calls || message.tool_calls.length === 0) {
      console.log(`\nGEMMA FINAL: ${message.content}`);
      return {
        success: true,
        answer: message.content,
        rounds: round + 1,
        usage: response.usage
      };
    }

    // Добавляем ответ ассистента в историю
    messages.push(choice.message);

    // Выполняем tool calls
    for (const toolCall of choice.message.tool_calls) {
      const fn = toolCall.function;
      console.log(`\nTOOL CALL: ${fn.name}`);
      console.log(`ARGS: ${fn.arguments}`);

      let args;
      try {
        args = JSON.parse(fn.arguments);
      } catch (e) {
        args = {};
      }

      let result;
      try {
        result = await mcp.callTool(fn.name, args);
        const content = result.content?.[0]?.text || JSON.stringify(result);
        console.log(`RESULT: ${content.substring(0, 200)}${content.length > 200 ? '...' : ''}`);
        messages.push({
          role: 'tool',
          tool_call_id: toolCall.id,
          content: content
        });
      } catch (e) {
        console.log(`ERROR: ${e.message}`);
        messages.push({
          role: 'tool',
          tool_call_id: toolCall.id,
          content: `Error: ${e.message}`
        });
      }
    }
  }

  return { success: false, answer: 'Max tool rounds exceeded', rounds: MAX_TOOL_ROUNDS };
}

async function main() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  const question = (prompt) => new Promise(resolve => rl.question(prompt, resolve));

  console.log('Gemma E2B ↔ comfyui-mcp Adapter');
  console.log('================================');
  console.log(`Llama URL: ${LLAMA_URL}`);
  console.log(`ComfyUI URL: ${COMFYUI_URL}`);
  console.log('');

  // Подключение к MCP
  console.log('Connecting to comfyui-mcp...');
  const mcp = new McpClient();

  try {
    const tools = await mcp.connect();
    console.log(`Connected! ${tools.length} tools available:`);
    tools.forEach(t => console.log(`  - ${t.name}`));
  } catch (e) {
    console.error(`Failed to connect to MCP: ${e.message}`);
    process.exit(1);
  }

  console.log('\nReady! Type your prompts (Ctrl+C to exit)\n');

  while (true) {
    const prompt = await question('> ');
    if (!prompt.trim()) continue;
    if (prompt.toLowerCase() === 'exit' || prompt.toLowerCase() === 'quit') break;

    try {
      const result = await runAgent(prompt, mcp);
      console.log(`\n[Completed in ${result.rounds} rounds, ${result.usage?.total_tokens || '?'} tokens]`);
    } catch (e) {
      console.error(`Error: ${e.message}`);
    }
  }

  mcp.disconnect();
  rl.close();
}

// CLI mode: передать промпт аргументом
if (process.argv.length > 2) {
  const prompt = process.argv.slice(2).join(' ');
  const mcp = new McpClient();
  mcp.connect().then(() => runAgent(prompt, mcp)).then(result => {
    console.log(JSON.stringify(result, null, 2));
    mcp.disconnect();
    process.exit(result.success ? 0 : 1);
  }).catch(e => {
    console.error(e);
    process.exit(1);
  });
} else {
  main();
}
