# M25 SteadIP Audit Report - Phase 1: Windows Client Test

## Executive Summary
SteadIP CLI installed and authenticated successfully, but frpc.exe execution is blocked
by the Windows security environment (WinError 5: Access Denied).

## Test Results

### 1. Windows Client
| Component | Status | Details |
|-----------|--------|---------|
| SteadIP CLI | PASS | v0.2.13 installed at C:\Users\1\AppData\Local\SteadIP\bin\ |
| Authentication | PASS | Logged in as olegluh1969@gmail.com (Free plan) |
| frpc.exe execution | FAIL | WinError 5: Access Denied |
| Tunnel creation | BLOCKED | Cannot start without frpc.exe |

### 2. Root Cause Analysis
The frpc.exe binary (16MB Go executable) is blocked at the OS level:
- Not an AppLocker restriction (no policy found)
- Not Windows Defender (no quarantine entries)
- Not a sandbox restriction (running on physical Windows 10 Pro)
- Likely: Enterprise security policy or application control software

Evidence:
- steadip.exe (same directory) runs fine
- Python executables run fine
- System32 executables run fine
- Only frpc.exe is blocked with "Access is denied"

### 3. Alternative: Colab Testing
Since local testing is blocked, proceed with Colab-based test:
- Origin (ComfyUI) is in Colab
- SteadIP client should run in Colab
- Test HTTP + WebSocket through SteadIP tunnel

## Next Steps
1. Run SteadIP in Colab with ComfyUI
2. Test HTTP endpoints (/system_stats, /object_info, /history)
3. Test WebSocket connectivity
4. Run M25 image.generate test
5. Evaluate hostname stability

## Conclusion
STADIP WINDOWS CLIENT = BLOCKED BY ENVIRONMENT
STADIP COLAB TEST = PENDING
