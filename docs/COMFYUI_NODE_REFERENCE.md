# ComfyUI Node Reference

> Auto-generated from /object_info | Nodes: 978
> Documented nodes: 63

---

## Table of Contents

- [By Category](#by-category)
- [All Nodes](#all-nodes)

---

## By Category

### 
- [wanBlockSwap](#wanblockswap)

### 3d
- [BuildPoseFile](#buildposefile)
- [CreateCameraInfo](#createcamerainfo)
- [Load3D](#load3d)
- [Load3DAdvanced](#load3dadvanced)
- [MeshToFile3D](#meshtofile3d)
- [Preview3D](#preview3d)
- [Preview3DAdvanced](#preview3dadvanced)
- [PreviewGaussianSplat](#previewgaussiansplat)
- [PreviewPointCloud](#previewpointcloud)
- [Save3DAdvanced](#save3dadvanced)
- [SaveGLB](#saveglb)
- [SaveGaussianSplat](#savegaussiansplat)
- [SavePointCloud](#savepointcloud)
- [VoxelToMesh](#voxeltomesh)
- [VoxelToMeshBasic](#voxeltomeshbasic)

### 3d/mesh
- [DecimateMesh](#decimatemesh)
- [FillHoles](#fillholes)
- [GetMeshInfo](#getmeshinfo)
- [MergeMeshes](#mergemeshes)
- [MeshSmoothNormals](#meshsmoothnormals)
- [PaintMesh](#paintmesh)
- [RemeshMesh](#remeshmesh)
- [RenderMesh](#rendermesh)
- [RotateMesh](#rotatemesh)
- [WeldVertices](#weldvertices)

### 3d/splat
- [File3DToSplat](#file3dtosplat)
- [GetSplatCount](#getsplatcount)
- [MergeSplat](#mergesplat)
- [RenderSplat](#rendersplat)
- [SplatToFile3D](#splattofile3d)
- [SplatToMesh](#splattomesh)
- [TransformSplat](#transformsplat)

### 3d/texturing
- [ApplyTextureToMesh](#applytexturetomesh)
- [BakeAmbientOcclusion](#bakeambientocclusion)
- [BakeNormalMapFromMesh](#bakenormalmapfrommesh)
- [BakeTextureFromVoxel](#baketexturefromvoxel)
- [MeshTextureToImage](#meshtexturetoimage)
- [RenderUVAtlas](#renderuvatlas)
- [UnwrapMesh](#unwrapmesh)

### LLM
- [OpenRouterNode](#openrouternode) ✓

### Pollinations/Audio
- [PollinationsAudioGen](#pollinationsaudiogen) ✓

### Pollinations/BYOP
- [PollinationsBYOPLogin](#pollinationsbyoplogin) ✓

### Pollinations/Image
- [PollinationsImageGen](#pollinationsimagegen) ✓

### Pollinations/Text
- [PollinationsTextGen](#pollinationstextgen) ✓

### Pollinations/Video
- [PollinationsVideoGen](#pollinationsvideogen) ✓

### QwenVL-F
- [QwenVL-F](#qwenvl-f)
- [QwenVL-F_Advanced](#qwenvl-f_advanced)
- [QwenVL-F_GGUF](#qwenvl-f_gguf)
- [QwenVL-F_GGUF_Advanced](#qwenvl-f_gguf_advanced)
- [QwenVL-F_PromptEnhancer](#qwenvl-f_promptenhancer)

### RequestNode/Converters
- [Audio To Blob Node](#audio-to-blob-node) ✓
- [Base64 To Audio Node](#base64-to-audio-node) ✓
- [Image To Base64 Node](#image-to-base64-node) ✓
- [Image To Blob Node](#image-to-blob-node) ✓
- [Video To Blob Node](#video-to-blob-node) ✓

### RequestNode/Get Request
- [Get Request Node](#get-request-node) ✓

### RequestNode/KeyValue
- [Key/Value Node](#key/value-node) ✓
- [Retry Settings Node](#retry-settings-node) ✓

### RequestNode/Post Request
- [Form Post Request Node](#form-post-request-node) ✓
- [Media Form Post Node](#media-form-post-node) ✓
- [Post Request Node](#post-request-node) ✓

### RequestNode/REST API
- [Binary Post Request Node](#binary-post-request-node) ✓
- [Rest Api Node](#rest-api-node) ✓

### RequestNode/Utils
- [Blob To Audio Node](#blob-to-audio-node) ✓
- [Blob To Batch Image Node](#blob-to-batch-image-node) ✓
- [Blob To Image Node](#blob-to-image-node) ✓
- [Blob To Video Node](#blob-to-video-node) ✓
- [Chainable Upload Image](#chainable-upload-image) ✓
- [String Replace Node](#string-replace-node) ✓

### Zho模块组/💫QWenVL
- [QWenVL_API_S_Multi_Zho](#qwenvl_api_s_multi_zho) ✓
- [QWenVL_API_S_Zho](#qwenvl_api_s_zho) ✓

### advanced/debug
- [EasyCache](#easycache)
- [LazyCache](#lazycache)
- [ModelComputeDtype](#modelcomputedtype)

### advanced/guidance
- [CFGNorm](#cfgnorm)
- [CFGZeroStar](#cfgzerostar)
- [LTXVModalityGuidance](#ltxvmodalityguidance)
- [LTXVSpatioTemporalGuidance](#ltxvspatiotemporalguidance)
- [NAGuidance](#naguidance)
- [SkipLayerGuidanceDiT](#skiplayerguidancedit)
- [SkipLayerGuidanceDiTSimple](#skiplayerguidanceditsimple)
- [SkipLayerGuidanceSD3](#skiplayerguidancesd3)
- [TCFG](#tcfg)

### advanced/hooks
- [ConditioningTimestepsRange](#conditioningtimestepsrange)

### advanced/hooks/clip
- [SetClipHooks](#setcliphooks)

### advanced/hooks/combine
- [CombineHooks2](#combinehooks2)
- [CombineHooks4](#combinehooks4)
- [CombineHooks8](#combinehooks8)

### advanced/hooks/cond pair
- [PairConditioningCombine](#pairconditioningcombine)
- [PairConditioningSetDefaultCombine](#pairconditioningsetdefaultcombine)
- [PairConditioningSetProperties](#pairconditioningsetproperties)
- [PairConditioningSetPropertiesAndCombine](#pairconditioningsetpropertiesandcombine)

### advanced/hooks/cond single
- [ConditioningSetDefaultCombine](#conditioningsetdefaultcombine)
- [ConditioningSetProperties](#conditioningsetproperties)
- [ConditioningSetPropertiesAndCombine](#conditioningsetpropertiesandcombine)

### advanced/hooks/create
- [CreateHookLora](#createhooklora)
- [CreateHookLoraModelOnly](#createhookloramodelonly)
- [CreateHookModelAsLora](#createhookmodelaslora)
- [CreateHookModelAsLoraModelOnly](#createhookmodelasloramodelonly)

### advanced/hooks/scheduling
- [CreateHookKeyframe](#createhookkeyframe)
- [CreateHookKeyframesFromFloats](#createhookkeyframesfromfloats)
- [CreateHookKeyframesInterpolated](#createhookkeyframesinterpolated)
- [SetHookKeyframes](#sethookkeyframes)

### advanced/multigpu
- [MultiGPU_WorkUnits](#multigpu_workunits)
- [SelectCLIPDevice](#selectclipdevice)
- [SelectModelDevice](#selectmodeldevice)
- [SelectVAEDevice](#selectvaedevice)

### api/text
- [OpenAICompatibleChat](#openaicompatiblechat) ✓

### audio
- [AudioAdjustVolume](#audioadjustvolume)
- [AudioConcat](#audioconcat)
- [AudioEqualizer3Band](#audioequalizer3band)
- [AudioMerge](#audiomerge)
- [EmptyAudio](#emptyaudio)
- [JoinAudioChannels](#joinaudiochannels)
- [LoadAudio](#loadaudio)
- [PreviewAudio](#previewaudio)
- [RecordAudio](#recordaudio)
- [SaveAudio](#saveaudio)
- [SaveAudioAdvanced](#saveaudioadvanced)
- [SaveAudioMP3](#saveaudiomp3)
- [SaveAudioOpus](#saveaudioopus)
- [SplitAudioChannels](#splitaudiochannels)
- [TrimAudioDuration](#trimaudioduration)

### comfy cloud/audio
- [ComfyCloudMiniMaxMusic3TextToAudioNode](#comfycloudminimaxmusic3texttoaudionode)

### comfy cloud/image
- [ComfyCloudFlux2TextToImageNode](#comfycloudflux2texttoimagenode)
- [ComfyCloudMageFlowTextToImageNode](#comfycloudmageflowtexttoimagenode)
- [ComfyCloudMageFlowTurboTextToImageNode](#comfycloudmageflowturbotexttoimagenode)
- [ComfyCloudZImageTurboNode](#comfycloudzimageturbonode)

### comfy cloud/video
- [ComfyCloudMiniMaxH3FirstLastFrameToVideoNode](#comfycloudminimaxh3firstlastframetovideonode)
- [ComfyCloudMiniMaxH3ImageToVideoNode](#comfycloudminimaxh3imagetovideonode)
- [ComfyCloudMiniMaxH3TextToVideoNode](#comfycloudminimaxh3texttovideonode)

### conditioning/video_models
- [LTXVDurationPredictor](#ltxvdurationpredictor)

### dataset/video
- [ShuffleVideoTextDataset](#shufflevideotextdataset)

### experimental
- [DifferentialDiffusion](#differentialdiffusion)
- [FluxKVCache](#fluxkvcache)
- [FreSca](#fresca)
- [LatentBlend](#latentblend)
- [LoraSave](#lorasave)
- [Mahiro](#mahiro)
- [PerpNeg](#perpneg)
- [PerpNegGuider](#perpnegguider)
- [SamplerEulerCFGpp](#samplereulercfgpp)
- [SelfAttentionGuidance](#selfattentionguidance)
- [TorchCompileModel](#torchcompilemodel)

### experimental/attention_experiments
- [CLIPAttentionMultiply](#clipattentionmultiply)
- [UNetCrossAttentionMultiply](#unetcrossattentionmultiply)
- [UNetSelfAttentionMultiply](#unetselfattentionmultiply)
- [UNetTemporalAttentionMultiply](#unettemporalattentionmultiply)

### experimental/stable cascade
- [StableCascade_SuperResolutionControlnet](#stablecascade_superresolutioncontrolnet)

### image
- [AddLayer](#addlayer)
- [EmptyImage](#emptyimage)
- [GetImageSize](#getimagesize)
- [ImageCompare](#imagecompare)
- [ImageCompositor](#imagecompositor)
- [LayersFromBoundingBoxes](#layersfromboundingboxes)
- [LoadImage](#loadimage)
- [LoadImageDataSetFromFolder](#loadimagedatasetfromfolder)
- [LoadImageMask](#loadimagemask)
- [LoadImageOutput](#loadimageoutput)
- [LoadImageTextDataSetFromFolder](#loadimagetextdatasetfromfolder)
- [Painter](#painter)
- [PreviewImage](#previewimage)
- [SaveAnimatedPNG](#saveanimatedpng)
- [SaveAnimatedWEBP](#saveanimatedwebp)
- [SaveImage](#saveimage)
- [SaveImageAdvanced](#saveimageadvanced)
- [SaveImageDataSetToFolder](#saveimagedatasettofolder)
- [SaveImageTextDataSetToFolder](#saveimagetextdatasettofolder)
- [SaveImageWebsocket](#saveimagewebsocket) ✓
- [SaveSVGNode](#savesvgnode)
- [WebcamCapture](#webcamcapture)

### image/adjustments
- [AdjustBrightness](#adjustbrightness)
- [AdjustContrast](#adjustcontrast)

### image/background removal
- [RemoveBackground](#removebackground)

### image/batch
- [BatchImagesNode](#batchimagesnode)
- [ImageBatch](#imagebatch)
- [ImageDeduplication](#imagededuplication)
- [ImageFromBatch](#imagefrombatch)
- [ImageGrid](#imagegrid)
- [ImageMergeTileList](#imagemergetilelist)
- [MergeImageLists](#mergeimagelists)
- [RebatchImages](#rebatchimages)
- [RepeatImageBatch](#repeatimagebatch)
- [ShuffleDataset](#shuffledataset)
- [ShuffleImageTextDataset](#shuffleimagetextdataset)
- [SplitImageToTileList](#splitimagetotilelist)

### image/color
- [ImageInvert](#imageinvert)
- [ImageRGBToYUV](#imagergbtoyuv)
- [ImageYUVToRGB](#imageyuvtorgb)
- [NormalizeImages](#normalizeimages)

### image/compositing
- [ImageCompositeMasked](#imagecompositemasked)
- [JoinImageWithAlpha](#joinimagewithalpha)
- [PorterDuffImageComposite](#porterduffimagecomposite)
- [SplitImageWithAlpha](#splitimagewithalpha)

### image/detection
- [DrawBBoxes](#drawbboxes)
- [MediaPipeFaceLandmarker](#mediapipefacelandmarker)
- [MediaPipeFaceMask](#mediapipefacemask)
- [MediaPipeFaceMeshVisualize](#mediapipefacemeshvisualize)
- [RTDETR_detect](#rtdetr_detect)
- [SAM3DBody_FaceExpression](#sam3dbody_faceexpression)
- [SAM3DBody_Loader](#sam3dbody_loader)
- [SAM3DBody_Predict](#sam3dbody_predict)
- [SAM3DBody_Render](#sam3dbody_render)
- [SAM3DBody_Smooth](#sam3dbody_smooth)
- [SAM3_Detect](#sam3_detect)
- [SAM3_TrackPreview](#sam3_trackpreview)
- [SAM3_TrackToMask](#sam3_tracktomask)
- [SAM3_VideoTrack](#sam3_videotrack)
- [SDPoseDrawKeypoints](#sdposedrawkeypoints)
- [SDPoseFaceBBoxes](#sdposefacebboxes)
- [SDPoseKeypointExtractor](#sdposekeypointextractor)

### image/filters
- [Canny](#canny)
- [ColorTransfer](#colortransfer)
- [ImageAddNoise](#imageaddnoise)
- [ImageBlend](#imageblend)
- [ImageBlur](#imageblur)
- [ImageQuantize](#imagequantize)
- [ImageSharpen](#imagesharpen)
- [Morphology](#morphology)

### image/geometry estimation
- [DA3GeometryToMesh](#da3geometrytomesh)
- [DA3Inference](#da3inference)
- [DA3Render](#da3render)
- [MoGeGeometryToFOV](#mogegeometrytofov)
- [MoGeInference](#mogeinference)
- [MoGePanoramaInference](#mogepanoramainference)
- [MoGePointMapToMesh](#mogepointmaptomesh)
- [MoGeRender](#mogerender)

### image/mask
- [BatchMasksNode](#batchmasksnode)
- [CropMask](#cropmask)
- [FeatherMask](#feathermask)
- [GrowMask](#growmask)
- [ImageColorToMask](#imagecolortomask)
- [ImageToMask](#imagetomask)
- [InvertMask](#invertmask)
- [MaskComposite](#maskcomposite)
- [MaskPreview](#maskpreview)
- [MaskToImage](#masktoimage)
- [SolidMask](#solidmask)
- [ThresholdMask](#thresholdmask)
- [VOIDQuadmaskPreprocess](#voidquadmaskpreprocess)

### image/post-processors
- [SeedVR2PostProcessing](#seedvr2postprocessing)

### image/pre-processors
- [SeedVR2Preprocess](#seedvr2preprocess)

### image/shader
- [GLSLShader](#glslshader)

### image/transform
- [CenterCropImages](#centercropimages)
- [CropByBBoxes](#cropbybboxes)
- [ImageCrop](#imagecrop)
- [ImageCropToMask](#imagecroptomask)
- [ImageCropV2](#imagecropv2)
- [ImageFlip](#imageflip)
- [ImagePadForOutpaint](#imagepadforoutpaint)
- [ImageRotate](#imagerotate)
- [ImageStitch](#imagestitch)
- [RandomCropImages](#randomcropimages)
- [ResizeAndPadImage](#resizeandpadimage)
- [ResizeImageMaskNode](#resizeimagemasknode)
- [ResizeImagesByLongerEdge](#resizeimagesbylongeredge)
- [ResizeImagesByShorterEdge](#resizeimagesbyshorteredge)

### image/upscaling
- [ImageScale](#imagescale)
- [ImageScaleBy](#imagescaleby)
- [ImageScaleToMaxDimension](#imagescaletomaxdimension)
- [ImageScaleToTotalPixels](#imagescaletototalpixels)
- [ImageUpscaleWithModel](#imageupscalewithmodel)

### image/video
- [WanDancerPadKeyframes](#wandancerpadkeyframes)
- [WanDancerPadKeyframesList](#wandancerpadkeyframeslist)

### model/conditioning
- [AudioEncoderEncode](#audioencoderencode)
- [CLIPSetLastLayer](#clipsetlastlayer)
- [CLIPTextEncode](#cliptextencode)
- [CLIPTextEncodeControlnet](#cliptextencodecontrolnet)
- [CLIPVisionEncode](#clipvisionencode)
- [InpaintModelConditioning](#inpaintmodelconditioning)
- [NormalizeVideoLatentStart](#normalizevideolatentstart)
- [PiDConditioning](#pidconditioning)
- [ReferenceLatent](#referencelatent)
- [ReferenceTimbreAudio](#referencetimbreaudio)
- [SeedVR2Conditioning](#seedvr2conditioning)
- [StyleModelApply](#stylemodelapply)
- [T5TokenizerOptions](#t5tokenizeroptions)
- [unCLIPConditioning](#unclipconditioning)

### model/conditioning/ace
- [TextEncodeAceStepAudio](#textencodeacestepaudio)
- [TextEncodeAceStepAudio1.5](#textencodeacestepaudio1.5)

### model/conditioning/autoregressive
- [ARVideoI2V](#arvideoi2v)

### model/conditioning/bernini
- [BerniniConditioning](#berniniconditioning)

### model/conditioning/boogu
- [TextEncodeBooguEdit](#textencodebooguedit)

### model/conditioning/controlnet
- [ControlNetApply](#controlnetapply)
- [ControlNetApplyAdvanced](#controlnetapplyadvanced)
- [ControlNetApplySD3](#controlnetapplysd3)
- [ControlNetInpaintingAliMamaApply](#controlnetinpaintingalimamaapply)
- [SetUnionControlNetType](#setunioncontrolnettype)

### model/conditioning/cosmos
- [CosmosImageToVideoLatent](#cosmosimagetovideolatent)
- [CosmosPredict2ImageToVideoLatent](#cosmospredict2imagetovideolatent)

### model/conditioning/flux
- [CLIPTextEncodeFlux](#cliptextencodeflux)
- [FluxDisableGuidance](#fluxdisableguidance)
- [FluxGuidance](#fluxguidance)
- [FluxKontextImageScale](#fluxkontextimagescale)
- [FluxKontextMultiReferenceLatentMethod](#fluxkontextmultireferencelatentmethod)

### model/conditioning/gligen
- [GLIGENTextBoxApply](#gligentextboxapply)

### model/conditioning/hidream
- [CLIPTextEncodeHiDream](#cliptextencodehidream)
- [HiDreamO1ReferenceImages](#hidreamo1referenceimages)

### model/conditioning/hunyuan 3d
- [Hunyuan3Dv2Conditioning](#hunyuan3dv2conditioning)
- [Hunyuan3Dv2ConditioningMultiView](#hunyuan3dv2conditioningmultiview)

### model/conditioning/hunyuan image
- [CLIPTextEncodeHunyuanDiT](#cliptextencodehunyuandit)

### model/conditioning/hunyuan video
- [HunyuanImageToVideo](#hunyuanimagetovideo)
- [HunyuanRefinerLatent](#hunyuanrefinerlatent)
- [HunyuanVideo15ImageToVideo](#hunyuanvideo15imagetovideo)
- [HunyuanVideo15SuperResolution](#hunyuanvideo15superresolution)
- [TextEncodeHunyuanVideo_ImageToVideo](#textencodehunyuanvideo_imagetovideo)

### model/conditioning/instructpix2pix
- [InstructPixToPixConditioning](#instructpixtopixconditioning)

### model/conditioning/joyimage
- [TextEncodeJoyImageEdit](#textencodejoyimageedit)

### model/conditioning/kandinsky
- [CLIPTextEncodeKandinsky5](#cliptextencodekandinsky5)
- [Kandinsky5ImageToVideo](#kandinsky5imagetovideo)

### model/conditioning/lotus
- [LotusConditioning](#lotusconditioning)

### model/conditioning/ltxv
- [GetICLoRAParameters](#geticloraparameters)
- [LTXVAddGuide](#ltxvaddguide)
- [LTXVConditioning](#ltxvconditioning)
- [LTXVCropGuides](#ltxvcropguides)
- [LTXVImgToVideo](#ltxvimgtovideo)
- [LTXVImgToVideoInplace](#ltxvimgtovideoinplace)
- [LTXVReferenceAudio](#ltxvreferenceaudio)

### model/conditioning/lumina
- [CLIPTextEncodeLumina2](#cliptextencodelumina2)

### model/conditioning/mage
- [TextEncodeMageFlowEdit](#textencodemageflowedit)

### model/conditioning/minimax
- [MiniMaxH3AddGuide](#minimaxh3addguide)
- [MiniMaxH3ImageToVideo](#minimaxh3imagetovideo)
- [MiniMaxH3ReferenceToVideo](#minimaxh3referencetovideo)

### model/conditioning/minimax music
- [MiniMaxMusic3TextEncode](#minimaxmusic3textencode)

### model/conditioning/photomaker
- [PhotoMakerEncode](#photomakerencode)

### model/conditioning/pixart
- [CLIPTextEncodePixArtAlpha](#cliptextencodepixartalpha)

### model/conditioning/qwen image
- [TextEncodeQwenImageEdit](#textencodeqwenimageedit)
- [TextEncodeQwenImageEditPlus](#textencodeqwenimageeditplus)

### model/conditioning/stable audio
- [ConditioningStableAudio](#conditioningstableaudio)

### model/conditioning/stable cascade
- [StableCascade_StageB_Conditioning](#stablecascade_stageb_conditioning)

### model/conditioning/stable diffusion
- [CLIPTextEncodeSD3](#cliptextencodesd3)
- [CLIPTextEncodeSDXL](#cliptextencodesdxl)
- [CLIPTextEncodeSDXLRefiner](#cliptextencodesdxlrefiner)

### model/conditioning/stable diffusion upscaler
- [SD_4XUpscale_Conditioning](#sd_4xupscale_conditioning)

### model/conditioning/stable video
- [SVD_img2vid_Conditioning](#svd_img2vid_conditioning)

### model/conditioning/stable video 3d
- [SV3D_Conditioning](#sv3d_conditioning)

### model/conditioning/stable zero123
- [StableZero123_Conditioning](#stablezero123_conditioning)
- [StableZero123_Conditioning_Batched](#stablezero123_conditioning_batched)

### model/conditioning/transform
- [ConditioningAverage](#conditioningaverage)
- [ConditioningCombine](#conditioningcombine)
- [ConditioningConcat](#conditioningconcat)
- [ConditioningMultiply](#conditioningmultiply)
- [ConditioningSetArea](#conditioningsetarea)
- [ConditioningSetAreaPercentage](#conditioningsetareapercentage)
- [ConditioningSetAreaPercentageVideo](#conditioningsetareapercentagevideo)
- [ConditioningSetAreaStrength](#conditioningsetareastrength)
- [ConditioningSetMask](#conditioningsetmask)
- [ConditioningSetTimestepRange](#conditioningsettimesteprange)
- [ConditioningZeroOut](#conditioningzeroout)

### model/conditioning/trellis2
- [Pixal3DConditioning](#pixal3dconditioning)
- [Trellis2Conditioning](#trellis2conditioning)
- [Trellis2ShapeStage](#trellis2shapestage)
- [Trellis2TextureStage](#trellis2texturestage)
- [Trellis2UpsampleStage](#trellis2upsamplestage)

### model/conditioning/triposplat
- [TripoSplatConditioning](#triposplatconditioning)
- [TripoSplatPreprocessImage](#triposplatpreprocessimage)

### model/conditioning/void
- [VOIDInpaintConditioning](#voidinpaintconditioning)

### model/conditioning/wan
- [Wan22ImageToVideoLatent](#wan22imagetovideolatent)
- [WanFirstLastFrameToVideo](#wanfirstlastframetovideo)
- [WanImageToVideo](#wanimagetovideo)

### model/conditioning/wan/animate
- [WanAnimate2Cache](#wananimate2cache)
- [WanAnimate2ToVideo](#wananimate2tovideo)
- [WanAnimateToVideo](#wananimatetovideo)

### model/conditioning/wan/camera
- [WanCameraEmbedding](#wancameraembedding)
- [WanCameraImageToVideo](#wancameraimagetovideo)

### model/conditioning/wan/dancer
- [WanDancerEncodeAudio](#wandancerencodeaudio)
- [WanDancerVideo](#wandancervideo)

### model/conditioning/wan/fun control
- [Wan22FunControlToVideo](#wan22funcontroltovideo)
- [WanFunControlToVideo](#wanfuncontroltovideo)

### model/conditioning/wan/fun inpaint
- [WanFunInpaintToVideo](#wanfuninpainttovideo)

### model/conditioning/wan/humo
- [WanHuMoImageToVideo](#wanhumoimagetovideo)

### model/conditioning/wan/infinite talk
- [WanInfiniteTalkToVideo](#waninfinitetalktovideo)

### model/conditioning/wan/move
- [GenerateTracks](#generatetracks)
- [WanMoveConcatTrack](#wanmoveconcattrack)
- [WanMoveTrackToVideo](#wanmovetracktovideo)
- [WanMoveTracksFromCoords](#wanmovetracksfromcoords)
- [WanMoveVisualizeTracks](#wanmovevisualizetracks)
- [WanTrackToVideo](#wantracktovideo)

### model/conditioning/wan/phantom subject
- [WanPhantomSubjectToVideo](#wanphantomsubjecttovideo)

### model/conditioning/wan/scail
- [SCAIL2ColoredMask](#scail2coloredmask)
- [WanSCAILToVideo](#wanscailtovideo)

### model/conditioning/wan/sound
- [WanSoundImageToVideo](#wansoundimagetovideo)
- [WanSoundImageToVideoExtend](#wansoundimagetovideoextend)

### model/conditioning/wan/vace
- [WanVaceToVideo](#wanvacetovideo)

### model/conditioning/z-image
- [TextEncodeZImageOmni](#textencodezimageomni)

### model/latent
- [EmptyLatentAudio](#emptylatentaudio)
- [EmptyLatentImage](#emptylatentimage)
- [LatentComposite](#latentcomposite)
- [LatentCompositeMasked](#latentcompositemasked)
- [LatentUpscale](#latentupscale)
- [LatentUpscaleBy](#latentupscaleby)
- [LoadLatent](#loadlatent)
- [SaveLatent](#savelatent)
- [SetLatentNoiseMask](#setlatentnoisemask)
- [TrimVideoLatent](#trimvideolatent)
- [VAEDecode](#vaedecode)
- [VAEDecodeAudio](#vaedecodeaudio)
- [VAEDecodeAudioTiled](#vaedecodeaudiotiled)
- [VAEDecodeTiled](#vaedecodetiled)
- [VAEEncode](#vaeencode)
- [VAEEncodeAudio](#vaeencodeaudio)
- [VAEEncodeForInpaint](#vaeencodeforinpaint)
- [VAEEncodeTiled](#vaeencodetiled)

### model/latent/ace
- [EmptyAceStep1.5LatentAudio](#emptyacestep1.5latentaudio)
- [EmptyAceStepLatentAudio](#emptyacesteplatentaudio)

### model/latent/advanced
- [LatentAdd](#latentadd)
- [LatentBatchSeedBehavior](#latentbatchseedbehavior)
- [LatentConcat](#latentconcat)
- [LatentCut](#latentcut)
- [LatentCutToBatch](#latentcuttobatch)
- [LatentInterpolate](#latentinterpolate)
- [LatentMultiply](#latentmultiply)
- [LatentSubtract](#latentsubtract)

### model/latent/advanced/operations
- [LatentApplyOperation](#latentapplyoperation)
- [LatentApplyOperationCFG](#latentapplyoperationcfg)
- [LatentOperationSharpen](#latentoperationsharpen)
- [LatentOperationTonemapReinhard](#latentoperationtonemapreinhard)

### model/latent/autoregressive
- [EmptyARVideoLatent](#emptyarvideolatent)

### model/latent/batch
- [BatchLatentsNode](#batchlatentsnode)
- [LatentBatch](#latentbatch)
- [LatentFromBatch](#latentfrombatch)
- [RebatchLatents](#rebatchlatents)
- [RepeatLatentBatch](#repeatlatentbatch)
- [ReplaceVideoLatentFrames](#replacevideolatentframes)
- [SeedVR2TemporalChunk](#seedvr2temporalchunk)
- [SeedVR2TemporalMerge](#seedvr2temporalmerge)

### model/latent/chroma radiance
- [EmptyChromaRadianceLatentImage](#emptychromaradiancelatentimage)

### model/latent/cosmos
- [EmptyCosmosLatentVideo](#emptycosmoslatentvideo)

### model/latent/flux
- [EmptyFlux2LatentImage](#emptyflux2latentimage)

### model/latent/hidream
- [EmptyHiDreamO1LatentImage](#emptyhidreamo1latentimage)

### model/latent/hunyhuan video
- [HunyuanVideo15LatentUpscaleWithModel](#hunyuanvideo15latentupscalewithmodel)

### model/latent/hunyuan 3d
- [EmptyLatentHunyuan3Dv2](#emptylatenthunyuan3dv2)
- [VAEDecodeHunyuan3D](#vaedecodehunyuan3d)

### model/latent/hunyuan image
- [EmptyHunyuanImageLatent](#emptyhunyuanimagelatent)

### model/latent/hunyuan video
- [EmptyHunyuanLatentVideo](#emptyhunyuanlatentvideo)
- [EmptyHunyuanVideo15Latent](#emptyhunyuanvideo15latent)

### model/latent/ltxv
- [EmptyLTXVLatentVideo](#emptyltxvlatentvideo)
- [LTXVAudioVAEDecode](#ltxvaudiovaedecode)
- [LTXVAudioVAEEncode](#ltxvaudiovaeencode)
- [LTXVConcatAVLatent](#ltxvconcatavlatent)
- [LTXVEmptyLatentAudio](#ltxvemptylatentaudio)
- [LTXVLatentUpsampler](#ltxvlatentupsampler)
- [LTXVSeparateAVLatent](#ltxvseparateavlatent)

### model/latent/minimax
- [EmptyMiniMaxH3LatentAV](#emptyminimaxh3latentav)

### model/latent/minimax music
- [EmptyMiniMaxMusic3LatentAudio](#emptyminimaxmusic3latentaudio)

### model/latent/mochi
- [EmptyMochiLatentVideo](#emptymochilatentvideo)

### model/latent/qwen
- [EmptyQwenImageLayeredLatentImage](#emptyqwenimagelayeredlatentimage)

### model/latent/stable cascade
- [StableCascade_EmptyLatentImage](#stablecascade_emptylatentimage)
- [StableCascade_StageC_VAEEncode](#stablecascade_stagec_vaeencode)

### model/latent/stable diffusion
- [EmptySD3LatentImage](#emptysd3latentimage)

### model/latent/transform
- [LatentCrop](#latentcrop)
- [LatentFlip](#latentflip)
- [LatentRotate](#latentrotate)

### model/latent/trellis
- [EmptyTrellis2LatentStructure](#emptytrellis2latentstructure)
- [VaeDecodeShapeTrellis](#vaedecodeshapetrellis)
- [VaeDecodeStructureTrellis2](#vaedecodestructuretrellis2)
- [VaeDecodeTextureTrellis](#vaedecodetexturetrellis)

### model/latent/triposplat
- [TripoSplatSamplingPreview](#triposplatsamplingpreview)
- [VAEDecodeTripoSplat](#vaedecodetriposplat)

### model/latent/void
- [VOIDWarpedNoise](#voidwarpednoise)
- [VOIDWarpedNoiseSource](#voidwarpednoisesource)

### model/loaders
- [AudioEncoderLoader](#audioencoderloader)
- [CLIPLoader](#cliploader)
- [CLIPVisionLoader](#clipvisionloader)
- [CheckpointLoader](#checkpointloader)
- [CheckpointLoaderSimple](#checkpointloadersimple)
- [ControlNetLoader](#controlnetloader)
- [DiffControlNetLoader](#diffcontrolnetloader)
- [DiffusersLoader](#diffusersloader)
- [DualCLIPLoader](#dualcliploader)
- [FrameInterpolationModelLoader](#frameinterpolationmodelloader)
- [GLIGENLoader](#gligenloader)
- [HypernetworkLoader](#hypernetworkloader)
- [ImageOnlyCheckpointLoader](#imageonlycheckpointloader)
- [LTXAVTextEncoderLoader](#ltxavtextencoderloader)
- [LTXVAudioVAELoader](#ltxvaudiovaeloader)
- [LatentUpscaleModelLoader](#latentupscalemodelloader)
- [LoadBackgroundRemovalModel](#loadbackgroundremovalmodel)
- [LoadDA3Model](#loadda3model)
- [LoadMediaPipeFaceLandmarker](#loadmediapipefacelandmarker)
- [LoadMoGeModel](#loadmogemodel)
- [LoraLoader](#loraloader)
- [LoraLoaderBypass](#loraloaderbypass)
- [LoraLoaderBypassModelOnly](#loraloaderbypassmodelonly)
- [LoraLoaderModelOnly](#loraloadermodelonly)
- [LoraModelLoader](#loramodelloader)
- [ModelPatchLoader](#modelpatchloader)
- [OpticalFlowLoader](#opticalflowloader)
- [PhotoMakerLoader](#photomakerloader)
- [QuadrupleCLIPLoader](#quadruplecliploader)
- [StyleModelLoader](#stylemodelloader)
- [TripleCLIPLoader](#triplecliploader)
- [UNETLoader](#unetloader)
- [UpscaleModelLoader](#upscalemodelloader)
- [VAELoader](#vaeloader)
- [unCLIPCheckpointLoader](#unclipcheckpointloader)

### model/merging
- [CLIPMergeAdd](#clipmergeadd)
- [CLIPMergeSimple](#clipmergesimple)
- [CLIPMergeSubtract](#clipmergesubtract)
- [CLIPSave](#clipsave)
- [CheckpointSave](#checkpointsave)
- [ImageOnlyCheckpointSave](#imageonlycheckpointsave)
- [ModelMergeAdd](#modelmergeadd)
- [ModelMergeBlocks](#modelmergeblocks)
- [ModelMergeSimple](#modelmergesimple)
- [ModelMergeSubtract](#modelmergesubtract)
- [ModelSave](#modelsave)
- [SaveLoRA](#savelora)
- [VAESave](#vaesave)

### model/merging/model specific
- [ModelMergeAuraflow](#modelmergeauraflow)
- [ModelMergeCosmos14B](#modelmergecosmos14b)
- [ModelMergeCosmos7B](#modelmergecosmos7b)
- [ModelMergeCosmosPredict2_14B](#modelmergecosmospredict2_14b)
- [ModelMergeCosmosPredict2_2B](#modelmergecosmospredict2_2b)
- [ModelMergeFlux1](#modelmergeflux1)
- [ModelMergeKrea2](#modelmergekrea2)
- [ModelMergeLTXV](#modelmergeltxv)
- [ModelMergeMochiPreview](#modelmergemochipreview)
- [ModelMergeQwenImage](#modelmergeqwenimage)
- [ModelMergeSD1](#modelmergesd1)
- [ModelMergeSD2](#modelmergesd2)
- [ModelMergeSD35_Large](#modelmergesd35_large)
- [ModelMergeSD3_2B](#modelmergesd3_2b)
- [ModelMergeSDXL](#modelmergesdxl)
- [ModelMergeWAN2_1](#modelmergewan2_1)

### model/patch
- [ContextWindowsManual](#contextwindowsmanual)
- [LTXVContextWindows](#ltxvcontextwindows)
- [ModelAttentionBackend](#modelattentionbackend)
- [ModelNoiseScale](#modelnoisescale)
- [ModelSamplingAuraFlow](#modelsamplingauraflow)
- [ModelSamplingContinuousEDM](#modelsamplingcontinuousedm)
- [ModelSamplingContinuousV](#modelsamplingcontinuousv)
- [ModelSamplingDiscrete](#modelsamplingdiscrete)
- [RenormCFG](#renormcfg)
- [RescaleCFG](#rescalecfg)
- [ScaleROPE](#scalerope)

### model/patch/chroma radiance
- [ChromaRadianceOptions](#chromaradianceoptions)

### model/patch/flux
- [ModelSamplingFlux](#modelsamplingflux)
- [USOStyleReference](#usostylereference)

### model/patch/hidream
- [HiDreamO1PatchSeamSmoothing](#hidreamo1patchseamsmoothing)

### model/patch/ltxv
- [ModelSamplingLTXV](#modelsamplingltxv)

### model/patch/minimax
- [MiniMaxH3SigmaShift](#minimaxh3sigmashift)

### model/patch/qwen
- [QwenImageDiffsynthControlnet](#qwenimagediffsynthcontrolnet)

### model/patch/stable cascade
- [ModelSamplingStableCascade](#modelsamplingstablecascade)

### model/patch/stable diffusion
- [ModelSamplingSD3](#modelsamplingsd3)

### model/patch/supir
- [SUPIRApply](#supirapply)

### model/patch/unet
- [Epsilon Scaling](#epsilon-scaling)
- [FreeU](#freeu)
- [FreeU_V2](#freeu_v2)
- [HyperTile](#hypertile)
- [PatchModelAddDownscale](#patchmodeladddownscale)
- [PerturbedAttentionGuidance](#perturbedattentionguidance)
- [TemporalScoreRescaling](#temporalscorerescaling)
- [TomePatchModel](#tomepatchmodel)

### model/patch/wan
- [WanContextWindowsManual](#wancontextwindowsmanual)
- [WanUni3CControlnetApply](#wanuni3ccontrolnetapply)

### model/patch/z-image
- [ZImageFunControlnet](#zimagefuncontrolnet)

### model/sampling
- [KSampler](#ksampler)
- [KSamplerAdvanced](#ksampleradvanced)

### model/sampling/custom
- [APG](#apg)
- [SamplerCustom](#samplercustom)
- [SamplerCustomAdvanced](#samplercustomadvanced)

### model/sampling/guiders
- [BasicGuider](#basicguider)
- [CFGGuider](#cfgguider)
- [CFGOverride](#cfgoverride)
- [DualCFGGuider](#dualcfgguider)
- [DualModelGuider](#dualmodelguider)
- [LTXVDualCFGGuider](#ltxvdualcfgguider)
- [VideoLinearCFGGuidance](#videolinearcfgguidance)
- [VideoTriangleCFGGuidance](#videotrianglecfgguidance)

### model/sampling/noise
- [AddNoise](#addnoise)
- [DisableNoise](#disablenoise)
- [RandomNoise](#randomnoise)

### model/sampling/samplers
- [KSamplerSelect](#ksamplerselect)
- [SamplerARVideo](#samplerarvideo)
- [SamplerDPMAdaptative](#samplerdpmadaptative)
- [SamplerDPMPP_2M_SDE](#samplerdpmpp_2m_sde)
- [SamplerDPMPP_2S_Ancestral](#samplerdpmpp_2s_ancestral)
- [SamplerDPMPP_3M_SDE](#samplerdpmpp_3m_sde)
- [SamplerDPMPP_SDE](#samplerdpmpp_sde)
- [SamplerER_SDE](#samplerer_sde)
- [SamplerEulerAncestral](#samplereulerancestral)
- [SamplerEulerAncestralCFGPP](#samplereulerancestralcfgpp)
- [SamplerLCM](#samplerlcm)
- [SamplerLCMUpscale](#samplerlcmupscale)
- [SamplerLMS](#samplerlms)
- [SamplerSASolver](#samplersasolver)
- [SamplerSEEDS2](#samplerseeds2)
- [VOIDSampler](#voidsampler)

### model/sampling/schedulers
- [AlignYourStepsScheduler](#alignyourstepsscheduler)
- [BasicScheduler](#basicscheduler)
- [BetaSamplingScheduler](#betasamplingscheduler)
- [ExponentialScheduler](#exponentialscheduler)
- [Flux2Scheduler](#flux2scheduler)
- [GITSScheduler](#gitsscheduler)
- [Ideogram4Scheduler](#ideogram4scheduler)
- [KarrasScheduler](#karrasscheduler)
- [LTXVScheduler](#ltxvscheduler)
- [LaplaceScheduler](#laplacescheduler)
- [OptimalStepsScheduler](#optimalstepsscheduler)
- [PolyexponentialScheduler](#polyexponentialscheduler)
- [SDTurboScheduler](#sdturboscheduler)
- [VPScheduler](#vpscheduler)

### model/sampling/sigmas
- [ExtendIntermediateSigmas](#extendintermediatesigmas)
- [FlipSigmas](#flipsigmas)
- [ManualSigmas](#manualsigmas)
- [SamplingPercentToSigma](#samplingpercenttosigma)
- [SetFirstSigma](#setfirstsigma)
- [SplitSigmas](#splitsigmas)
- [SplitSigmasDenoise](#splitsigmasdenoise)

### model/training
- [LoadTrainingDataset](#loadtrainingdataset)
- [LossGraphNode](#lossgraphnode)
- [MakeTrainingDataset](#maketrainingdataset)
- [ResolutionBucket](#resolutionbucket)
- [SaveTrainingDataset](#savetrainingdataset)
- [TrainLoraNode](#trainloranode)

### model_patches/anima
- [AnimaLLLiteApply](#animallliteapply)

### partner/3d/Meshy
- [MeshyAnimateModelNode](#meshyanimatemodelnode)
- [MeshyImageToModelNode](#meshyimagetomodelnode)
- [MeshyMultiImageToModelNode](#meshymultiimagetomodelnode)
- [MeshyRefineNode](#meshyrefinenode)
- [MeshyRigModelNode](#meshyrigmodelnode)
- [MeshyTextToModelNode](#meshytexttomodelnode)
- [MeshyTextureMultiViewNode](#meshytexturemultiviewnode)
- [MeshyTextureNode](#meshytexturenode)

### partner/3d/Rodin
- [Rodin3D_Detail](#rodin3d_detail)
- [Rodin3D_Gen2](#rodin3d_gen2)
- [Rodin3D_Gen25_Image](#rodin3d_gen25_image)
- [Rodin3D_Gen25_Text](#rodin3d_gen25_text)
- [Rodin3D_Regular](#rodin3d_regular)
- [Rodin3D_Sketch](#rodin3d_sketch)
- [Rodin3D_Smooth](#rodin3d_smooth)

### partner/3d/Tencent
- [Tencent3DPartNode](#tencent3dpartnode)
- [Tencent3DTextureEditNode](#tencent3dtextureeditnode)
- [TencentImageToModelNode](#tencentimagetomodelnode)
- [TencentModelTo3DUVNode](#tencentmodelto3duvnode)
- [TencentSmartTopologyNode](#tencentsmarttopologynode)
- [TencentTextToModelNode](#tencenttexttomodelnode)

### partner/3d/Tripo
- [TripoConversionNode](#tripoconversionnode)
- [TripoEditMultiviewNode](#tripoeditmultiviewnode)
- [TripoImageToModelNode](#tripoimagetomodelnode)
- [TripoImageToMultiviewNode](#tripoimagetomultiviewnode)
- [TripoImportModelNode](#tripoimportmodelnode)
- [TripoMeshCompleteNode](#tripomeshcompletenode)
- [TripoMultiviewToModelNode](#tripomultiviewtomodelnode)
- [TripoP1ImageToModelNode](#tripop1imagetomodelnode)
- [TripoP1MultiviewToModelNode](#tripop1multiviewtomodelnode)
- [TripoP1TextToModelNode](#tripop1texttomodelnode)
- [TripoRetargetNode](#triporetargetnode)
- [TripoRetopologyNode](#triporetopologynode)
- [TripoRigCheckNode](#triporigchecknode)
- [TripoRigNode](#triporignode)
- [TripoSegmentNode](#triposegmentnode)
- [TripoTextToModelNode](#tripotexttomodelnode)
- [TripoTextureNode](#tripotexturenode)

### partner/audio/ByteDance
- [ByteDanceSeedAudio](#bytedanceseedaudio)

### partner/audio/ElevenLabs
- [ElevenLabsAudioIsolation](#elevenlabsaudioisolation)
- [ElevenLabsInstantVoiceClone](#elevenlabsinstantvoiceclone)
- [ElevenLabsSpeechToSpeech](#elevenlabsspeechtospeech)
- [ElevenLabsSpeechToText](#elevenlabsspeechtotext)
- [ElevenLabsTextToDialogue](#elevenlabstexttodialogue)
- [ElevenLabsTextToSoundEffects](#elevenlabstexttosoundeffects)
- [ElevenLabsTextToSpeech](#elevenlabstexttospeech)
- [ElevenLabsVoiceSelector](#elevenlabsvoiceselector)

### partner/audio/Fish Audio
- [FishAudioInstantVoiceClone](#fishaudioinstantvoiceclone)
- [FishAudioSpeechToText](#fishaudiospeechtotext)
- [FishAudioTextToSpeech](#fishaudiotexttospeech)
- [FishAudioVoiceSelector](#fishaudiovoiceselector)

### partner/audio/HeyGen
- [HeyGenTextToSpeechNode](#heygentexttospeechnode)

### partner/audio/Sonilo
- [SoniloTextToMusic](#sonilotexttomusic)
- [SoniloVideoToMusic](#sonilovideotomusic)

### partner/image/BFL
- [Flux2ImageNode](#flux2imagenode)
- [Flux2MaxImageNode](#flux2maximagenode)
- [Flux2ProImageNode](#flux2proimagenode)
- [FluxEraseNode](#fluxerasenode)
- [FluxKontextMaxImageNode](#fluxkontextmaximagenode)
- [FluxKontextProImageNode](#fluxkontextproimagenode)
- [FluxProExpandNode](#fluxproexpandnode)
- [FluxProFillNode](#fluxprofillnode)
- [FluxProUltraImageNode](#fluxproultraimagenode)
- [FluxVTONode](#fluxvtonode)

### partner/image/Beeble
- [BeebleSwitchXImageEdit](#beebleswitchximageedit)

### partner/image/Bria
- [BriaEraser](#briaeraser)
- [BriaExpandImage](#briaexpandimage)
- [BriaGenFill](#briagenfill)
- [BriaImageEditNode](#briaimageeditnode)
- [BriaIncreaseResolution](#briaincreaseresolution)
- [BriaRemoveImageBackground](#briaremoveimagebackground)

### partner/image/ByteDance
- [ByteDanceCreateImageAsset](#bytedancecreateimageasset)
- [ByteDanceImageNode](#bytedanceimagenode)
- [ByteDanceSeedreamLayerSeparationNode](#bytedanceseedreamlayerseparationnode)
- [ByteDanceSeedreamNode](#bytedanceseedreamnode)
- [ByteDanceSeedreamNodeV2](#bytedanceseedreamnodev2)
- [ByteDanceSeedreamNodeV3](#bytedanceseedreamnodev3)

### partner/image/Gemini
- [GeminiImage2Node](#geminiimage2node)
- [GeminiImageNode](#geminiimagenode)
- [GeminiNanoBanana2](#gemininanobanana2)
- [GeminiNanoBanana2V2](#gemininanobanana2v2)

### partner/image/Grok
- [GrokImageEditNode](#grokimageeditnode)
- [GrokImageEditNodeV2](#grokimageeditnodev2)
- [GrokImageNode](#grokimagenode)

### partner/image/HitPaw
- [HitPawGeneralImageEnhance](#hitpawgeneralimageenhance)

### partner/image/Ideogram
- [IdeogramPImage](#ideogrampimage)
- [IdeogramV3](#ideogramv3)
- [IdeogramV4](#ideogramv4)

### partner/image/Kling
- [KlingImageGenerationNode](#klingimagegenerationnode)
- [KlingOmniProImageNode](#klingomniproimagenode)

### partner/image/Krea
- [Krea2ImageNode](#krea2imagenode)
- [Krea2StyleReferenceNode](#krea2stylereferencenode)

### partner/image/Luma
- [LumaImageEditNode2](#lumaimageeditnode2)
- [LumaImageModifyNode](#lumaimagemodifynode)
- [LumaImageNode](#lumaimagenode)
- [LumaImageNode2](#lumaimagenode2)
- [LumaReferenceNode](#lumareferencenode)

### partner/image/Magnific
- [MagnificImageRelightNode](#magnificimagerelightnode)
- [MagnificImageSkinEnhancerNode](#magnificimageskinenhancernode)
- [MagnificImageStyleTransferNode](#magnificimagestyletransfernode)
- [MagnificImageUpscalerCreativeNode](#magnificimageupscalercreativenode)
- [MagnificImageUpscalerPreciseV2Node](#magnificimageupscalerprecisev2node)

### partner/image/Meta
- [MetaMuseImageEditApi](#metamuseimageeditapi)
- [MetaMuseImageTextToImageApi](#metamuseimagetexttoimageapi)

### partner/image/OpenAI
- [OpenAIDalle2](#openaidalle2)
- [OpenAIDalle3](#openaidalle3)
- [OpenAIGPTImage1](#openaigptimage1)
- [OpenAIGPTImageNodeV2](#openaigptimagenodev2)

### partner/image/Quiver
- [QuiverImageToSVGNode](#quiverimagetosvgnode)
- [QuiverTextToSVGNode](#quivertexttosvgnode)

### partner/image/Qwen
- [QwenImageEditApi](#qwenimageeditapi)
- [QwenImageTextToImageApi](#qwenimagetexttoimageapi)

### partner/image/Recraft
- [RecraftColorRGB](#recraftcolorrgb)
- [RecraftControls](#recraftcontrols)
- [RecraftCreateStyleNode](#recraftcreatestylenode)
- [RecraftCreativeUpscaleNode](#recraftcreativeupscalenode)
- [RecraftCrispUpscaleNode](#recraftcrispupscalenode)
- [RecraftImageInpaintingNode](#recraftimageinpaintingnode)
- [RecraftImageToImageNode](#recraftimagetoimagenode)
- [RecraftRemoveBackgroundNode](#recraftremovebackgroundnode)
- [RecraftReplaceBackgroundNode](#recraftreplacebackgroundnode)
- [RecraftStyleV3DigitalIllustration](#recraftstylev3digitalillustration)
- [RecraftStyleV3InfiniteStyleLibrary](#recraftstylev3infinitestylelibrary)
- [RecraftStyleV3LogoRaster](#recraftstylev3logoraster)
- [RecraftStyleV3RealisticImage](#recraftstylev3realisticimage)
- [RecraftTextToImageNode](#recrafttexttoimagenode)
- [RecraftTextToVectorNode](#recrafttexttovectornode)
- [RecraftV4CreateStyleNode](#recraftv4createstylenode)
- [RecraftV4TextToImageNode](#recraftv4texttoimagenode)
- [RecraftV4TextToVectorNode](#recraftv4texttovectornode)
- [RecraftVectorizeImageNode](#recraftvectorizeimagenode)

### partner/image/Reve
- [ReveImageCreateNode](#reveimagecreatenode)
- [ReveImageEditNode](#reveimageeditnode)
- [ReveImageRemixNode](#reveimageremixnode)

### partner/image/Runway
- [RunwayTextToImageNode](#runwaytexttoimagenode)

### partner/image/Topaz
- [TopazImageEnhance](#topazimageenhance)
- [TopazImageEnhanceV2](#topazimageenhancev2)

### partner/image/Wan
- [WanImageToImageApi](#wanimagetoimageapi)
- [WanTextToImageApi](#wantexttoimageapi)

### partner/image/WaveSpeed
- [WavespeedImageUpscaleNode](#wavespeedimageupscalenode)

### partner/text/Anthropic
- [ClaudeNode](#claudenode)

### partner/text/ByteDance
- [ByteDanceSeedNode](#bytedanceseednode)

### partner/text/Gemini
- [GeminiInputFiles](#geminiinputfiles)
- [GeminiNode](#gemininode)
- [GeminiNodeV2](#gemininodev2)

### partner/text/OpenAI
- [OpenAIChatConfig](#openaichatconfig)
- [OpenAIChatNode](#openaichatnode)
- [OpenAIInputFiles](#openaiinputfiles)

### partner/text/OpenRouter
- [OpenRouterLLMNode](#openrouterllmnode)

### partner/video/BFL
- [Flux3ImageToVideoNode](#flux3imagetovideonode)
- [Flux3TextToVideoNode](#flux3texttovideonode)
- [Flux3VideoContinuationNode](#flux3videocontinuationnode)
- [FluxVideoUpscaleNode](#fluxvideoupscalenode)

### partner/video/Beeble
- [BeebleSwitchXVideoEdit](#beebleswitchxvideoedit)

### partner/video/Bria
- [BriaRemoveVideoBackground](#briaremovevideobackground)
- [BriaTransparentVideoBackground](#briatransparentvideobackground)
- [BriaVideoGreenScreen](#briavideogreenscreen)
- [BriaVideoReplaceBackground](#briavideoreplacebackground)

### partner/video/ByteDance
- [ByteDance2FirstLastFrameNode](#bytedance2firstlastframenode)
- [ByteDance2ReferenceNode](#bytedance2referencenode)
- [ByteDance2ReferenceNodeV2](#bytedance2referencenodev2)
- [ByteDance2TextToVideoNode](#bytedance2texttovideonode)
- [ByteDanceCreateVideoAsset](#bytedancecreatevideoasset)
- [ByteDanceFirstLastFrameNode](#bytedancefirstlastframenode)
- [ByteDanceImageReferenceNode](#bytedanceimagereferencenode)
- [ByteDanceImageToVideoNode](#bytedanceimagetovideonode)
- [ByteDanceTextToVideoNode](#bytedancetexttovideonode)
- [ByteDanceVideoEnhanceNode](#bytedancevideoenhancenode)

### partner/video/Gemini
- [GeminiVideoOmni](#geminivideoomni)
- [GeminiVideoOmniV2](#geminivideoomniv2)

### partner/video/Grok
- [GrokVideoEditNode](#grokvideoeditnode)
- [GrokVideoExtendNode](#grokvideoextendnode)
- [GrokVideoNode](#grokvideonode)
- [GrokVideoReferenceNode](#grokvideoreferencenode)

### partner/video/HeyGen
- [HeyGenAvatarVideoNode](#heygenavatarvideonode)
- [HeyGenCreateAvatarNode](#heygencreateavatarnode)
- [HeyGenTalkingPhotoNode](#heygentalkingphotonode)
- [HeyGenVideoTranslateNode](#heygenvideotranslatenode)

### partner/video/HitPaw
- [HitPawVideoEnhance](#hitpawvideoenhance)

### partner/video/Kling
- [KlingAvatarNode](#klingavatarnode)
- [KlingFirstLastFrameNode](#klingfirstlastframenode)
- [KlingImage2VideoNode](#klingimage2videonode)
- [KlingImageToVideoWithAudio](#klingimagetovideowithaudio)
- [KlingLipSyncAudioToVideoNode](#klinglipsyncaudiotovideonode)
- [KlingLipSyncTextToVideoNode](#klinglipsynctexttovideonode)
- [KlingMotionControl](#klingmotioncontrol)
- [KlingOmniProEditVideoNode](#klingomniproeditvideonode)
- [KlingOmniProFirstLastFrameNode](#klingomniprofirstlastframenode)
- [KlingOmniProImageToVideoNode](#klingomniproimagetovideonode)
- [KlingOmniProTextToVideoNode](#klingomniprotexttovideonode)
- [KlingOmniProVideoToVideoNode](#klingomniprovideotovideonode)
- [KlingStartEndFrameNode](#klingstartendframenode)
- [KlingTextToVideoNode](#klingtexttovideonode)
- [KlingTextToVideoWithAudio](#klingtexttovideowithaudio)
- [KlingVideoExtendNode](#klingvideoextendnode)
- [KlingVideoNode](#klingvideonode)

### partner/video/LTXV
- [LtxApi25AudioToVideo](#ltxapi25audiotovideo)
- [LtxApi25ImageToVideo](#ltxapi25imagetovideo)
- [LtxApi25TextToVideo](#ltxapi25texttovideo)
- [LtxvApiImageToVideo](#ltxvapiimagetovideo)
- [LtxvApiTextToVideo](#ltxvapitexttovideo)

### partner/video/Luma
- [LumaConceptsNode](#lumaconceptsnode)
- [LumaImageToVideoNode](#lumaimagetovideonode)
- [LumaRay32ExtendVideoNode](#lumaray32extendvideonode)
- [LumaRay32ImageToVideoNode](#lumaray32imagetovideonode)
- [LumaRay32KeyframeNode](#lumaray32keyframenode)
- [LumaRay32KeyframesToVideoNode](#lumaray32keyframestovideonode)
- [LumaRay32TextToVideoNode](#lumaray32texttovideonode)
- [LumaRay32VideoEditNode](#lumaray32videoeditnode)
- [LumaRay32VideoReframeNode](#lumaray32videoreframenode)
- [LumaVideoNode](#lumavideonode)

### partner/video/MiniMax
- [MinimaxHailuo03ContextIRNode](#minimaxhailuo03contextirnode)
- [MinimaxHailuo03FirstLastFrameNode](#minimaxhailuo03firstlastframenode)
- [MinimaxHailuo03ReferenceNode](#minimaxhailuo03referencenode)
- [MinimaxHailuo03RegenerateNode](#minimaxhailuo03regeneratenode)
- [MinimaxHailuo03TextToVideoNode](#minimaxhailuo03texttovideonode)
- [MinimaxHailuoVideoNode](#minimaxhailuovideonode)
- [MinimaxImageToVideoNode](#minimaximagetovideonode)
- [MinimaxTextToVideoNode](#minimaxtexttovideonode)

### partner/video/PixVerse
- [PixverseImageToVideoNode](#pixverseimagetovideonode)
- [PixverseTemplateNode](#pixversetemplatenode)
- [PixverseTextToVideoNode](#pixversetexttovideonode)
- [PixverseTransitionVideoNode](#pixversetransitionvideonode)
- [PixverseV6ExtendVideoNode](#pixversev6extendvideonode)
- [PixverseV6FirstLastFrameNode](#pixversev6firstlastframenode)
- [PixverseV6FusionVideoNode](#pixversev6fusionvideonode)
- [PixverseV6ImageToVideoNode](#pixversev6imagetovideonode)
- [PixverseV6TextToVideoNode](#pixversev6texttovideonode)

### partner/video/Runway
- [RunwayAleph2KeyframeNode](#runwayaleph2keyframenode)
- [RunwayAleph2PromptImageNode](#runwayaleph2promptimagenode)
- [RunwayAleph2VideoToVideoNode](#runwayaleph2videotovideonode)
- [RunwayFirstLastFrameNode](#runwayfirstlastframenode)
- [RunwayImageToVideoNodeGen3a](#runwayimagetovideonodegen3a)
- [RunwayImageToVideoNodeGen4](#runwayimagetovideonodegen4)

### partner/video/Sora
- [OpenAIVideoSora2](#openaivideosora2)

### partner/video/Topaz
- [TopazVideoEnhance](#topazvideoenhance)
- [TopazVideoEnhanceV2](#topazvideoenhancev2)

### partner/video/Veo
- [Veo3FirstLastFrameNode](#veo3firstlastframenode)
- [Veo3VideoGenerationNode](#veo3videogenerationnode)

### partner/video/Vidu
- [Vidu2ImageToVideoNode](#vidu2imagetovideonode)
- [Vidu2ReferenceVideoNode](#vidu2referencevideonode)
- [Vidu2StartEndToVideoNode](#vidu2startendtovideonode)
- [Vidu2TextToVideoNode](#vidu2texttovideonode)
- [Vidu3ImageToVideoNode](#vidu3imagetovideonode)
- [Vidu3StartEndToVideoNode](#vidu3startendtovideonode)
- [Vidu3TextToVideoNode](#vidu3texttovideonode)
- [ViduExtendVideoNode](#viduextendvideonode)
- [ViduImageToVideoNode](#viduimagetovideonode)
- [ViduMultiFrameVideoNode](#vidumultiframevideonode)
- [ViduReferenceVideoNode](#vidureferencevideonode)
- [ViduStartEndToVideoNode](#vidustartendtovideonode)
- [ViduTextToVideoNode](#vidutexttovideonode)

### partner/video/Wan
- [HappyHorseImageToVideoApi](#happyhorseimagetovideoapi)
- [HappyHorseReferenceVideoApi](#happyhorsereferencevideoapi)
- [HappyHorseTextToVideoApi](#happyhorsetexttovideoapi)
- [HappyHorseVideoEditApi](#happyhorsevideoeditapi)
- [Wan2ImageToVideoApi](#wan2imagetovideoapi)
- [Wan2ReferenceVideoApi](#wan2referencevideoapi)
- [Wan2TextToVideoApi](#wan2texttovideoapi)
- [Wan2VideoContinuationApi](#wan2videocontinuationapi)
- [Wan2VideoEditApi](#wan2videoeditapi)
- [Wan3ImageToVideoApi](#wan3imagetovideoapi)
- [Wan3ReferenceToVideoApi](#wan3referencetovideoapi)
- [WanImageToVideoApi](#wanimagetovideoapi)
- [WanReferenceVideoApi](#wanreferencevideoapi)
- [WanTextToVideoApi](#wantexttovideoapi)

### partner/video/WaveSpeed
- [WavespeedFlashVSRNode](#wavespeedflashvsrnode)

### partner/video/sync.so
- [SyncLipSyncNode](#synclipsyncnode)
- [SyncTalkingImageNode](#synctalkingimagenode)

### text
- [AddTextPrefix](#addtextprefix)
- [AddTextSuffix](#addtextsuffix)
- [BuildJsonPromptIdeogram](#buildjsonpromptideogram)
- [CaseConverter](#caseconverter)
- [ConvertArrayToString](#convertarraytostring)
- [ConvertDictionaryToString](#convertdictionarytostring)
- [JsonExtractString](#jsonextractstring)
- [MergeTextLists](#mergetextlists)
- [RegexExtract](#regexextract)
- [RegexMatch](#regexmatch)
- [RegexReplace](#regexreplace)
- [ReplaceText](#replacetext)
- [SaveText](#savetext)
- [StringCompare](#stringcompare)
- [StringConcatenate](#stringconcatenate)
- [StringContains](#stringcontains)
- [StringFormat](#stringformat)
- [StringLength](#stringlength)
- [StringReplace](#stringreplace)
- [StringSubstring](#stringsubstring)
- [StringTrim](#stringtrim)
- [StripWhitespace](#stripwhitespace)
- [TextGenerate](#textgenerate)
- [TextGenerateLTX2Prompt](#textgenerateltx2prompt)
- [TextOverlay](#textoverlay)
- [TextToLowercase](#texttolowercase)
- [TextToUppercase](#texttouppercase)
- [TruncateText](#truncatetext)

### utilities
- [ColorToRGBInt](#colortorgbint)
- [ComfyMathExpression](#comfymathexpression)
- [ComfyNumberConvert](#comfynumberconvert)
- [CreateBoundingBoxes](#createboundingboxes)
- [CreateList](#createlist)
- [CurveEditor](#curveeditor)
- [CustomCombo](#customcombo)
- [ImageHistogram](#imagehistogram)
- [PreviewAny](#previewany)
- [ResolutionSelector](#resolutionselector)
- [SeedNode](#seednode)

### utilities/logic
- [ComfyAndNode](#comfyandnode)
- [ComfyNotNode](#comfynotnode)
- [ComfyOrNode](#comfyornode)
- [ComfySwitchNode](#comfyswitchnode)

### utilities/primitive
- [PrimitiveBoolean](#primitiveboolean)
- [PrimitiveBoundingBox](#primitiveboundingbox)
- [PrimitiveFloat](#primitivefloat)
- [PrimitiveInt](#primitiveint)
- [PrimitiveString](#primitivestring)
- [PrimitiveStringMultiline](#primitivestringmultiline)

### video
- [CreateVideo](#createvideo)
- [FrameInterpolate](#frameinterpolate)
- [GetVideoComponents](#getvideocomponents)
- [LoadVideo](#loadvideo)
- [LoadVideoDataSetFromFolder](#loadvideodatasetfromfolder)
- [LoadVideoTextDataSetFromFolder](#loadvideotextdatasetfromfolder)
- [SaveVideo](#savevideo)
- [SaveWEBM](#savewebm)
- [Video Slice](#video-slice)
- [VideoFrameSample](#videoframesample)

### video/batch
- [ShuffleVideoDataset](#shufflevideodataset)

### video/preprocessors
- [LTXVPreprocess](#ltxvpreprocess)

### video/transform
- [VideoRandomTemporalCrop](#videorandomtemporalcrop)
- [VideoTemporalCrop](#videotemporalcrop)

### 🌌 ReActor
- [ImageRGBA2RGB](#imagergba2rgb) ✓
- [ReActorBuildFaceModel](#reactorbuildfacemodel)
- [ReActorFaceBoost](#reactorfaceboost) ✓
- [ReActorFaceSimilarity](#reactorfacesimilarity) ✓
- [ReActorFaceSwap](#reactorfaceswap)
- [ReActorFaceSwapOpt](#reactorfaceswapopt)
- [ReActorImageDublicator](#reactorimagedublicator)
- [ReActorLoadFaceModel](#reactorloadfacemodel)
- [ReActorMakeFaceModelBatch](#reactormakefacemodelbatch)
- [ReActorMaskHelper](#reactormaskhelper)
- [ReActorOptions](#reactoroptions) ✓
- [ReActorRestoreFace](#reactorrestoreface)
- [ReActorRestoreFaceAdvanced](#reactorrestorefaceadvanced)
- [ReActorSaveFaceModel](#reactorsavefacemodel)
- [ReActorSetWeight](#reactorsetweight)
- [ReActorUnload](#reactorunload) ✓

### 🤖QWEN3VL_API
- [LoadImageFromFolder](#loadimagefromfolder) ✓
- [LoadVideoFromFolder](#loadvideofromfolder) ✓
- [QWEN3VL_Image](#qwen3vl_image) ✓
- [QWEN3VL_Video](#qwen3vl_video) ✓
- [QWEN3_Text](#qwen3_text) ✓
- [QWEN_APIKey](#qwen_apikey) ✓
- [QWEN_TextDisplay](#qwen_textdisplay)
- [QWEN_TextOperation](#qwen_textoperation) ✓
- [QWEN_TextProcess](#qwen_textprocess) ✓

### 🧪AILab/⚡Agnes-AI
- [AgnesImage](#agnesimage) ✓
- [AgnesText](#agnestext) ✓
- [AgnesVideo](#agnesvideo) ✓

---

## All Nodes

### APG

- **Category:** model/sampling/custom
- **Documented:** No

---

### ARVideoI2V

- **Category:** model/conditioning/autoregressive
- **Documented:** No

---

### AddLayer

- **Category:** image
- **Documented:** No

---

### AddNoise

- **Category:** model/sampling/noise
- **Documented:** No

---

### AddTextPrefix

- **Category:** text
- **Documented:** No

---

### AddTextSuffix

- **Category:** text
- **Documented:** No

---

### AdjustBrightness

- **Category:** image/adjustments
- **Documented:** No

---

### AdjustContrast

- **Category:** image/adjustments
- **Documented:** No

---

### AgnesImage

- **Category:** 🧪AILab/⚡Agnes-AI
- **Documented:** Yes

**Purpose:** Генерация изображений через Agnes API

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| prompt | STRING |  | Текст-промпт для генерации |
| quality | ['1K', '2K', '4K'] | 1K | Качество |
| aspect_ratio | ['auto', '1:1', '2:3', '3:4', '4:5', '9:16', '9:21', '3:2', '4:3', '5:4', '16:9', '21:9'] | auto |  |

**Outputs:**
- `images` (IMAGE): 

**Configuration:**
- API key: через `agnes_config.json`

**Related:** AgnesVideo, AgnesText

---

### AgnesText

- **Category:** 🧪AILab/⚡Agnes-AI
- **Documented:** Yes

**Purpose:** Генерация текста через Agnes API

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| preset | ['Prompt Enhance', 'Translate to English', 'Extract Art Style from Image', 'Image Detailed Description'] | Prompt Enhance |  |
| prompt | STRING |  | Текст-промпт |

**Outputs:**
- `output` (STRING): 

**Related:** AgnesImage, AgnesVideo

---

### AgnesVideo

- **Category:** 🧪AILab/⚡Agnes-AI
- **Documented:** Yes

**Purpose:** Генерация видео через Agnes API (текст→видео, изображение→видео)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| mode | ['Text To Video', 'Image To Video', 'First and Last frame'] | Text To Video | Режим генерации |
| prompt | STRING |  | Текст-промпт для генерации |
| quality | ['480p', '720p', '1080p'] | 720p | Качество видео |
| aspect_ratio | ['auto', '1:1', '2:3', '3:4', '4:5', '9:16', '9:21', '3:2', '4:3', '5:4', '16:9', '21:9'] | auto |  |
| duration | FLOAT | 5.0 | Длительность в секундах |
| frame_rate | INT | 24 |  |
| seed | INT | 0 | Сид для воспроизводимости |

**Outputs:**
- `video` (VIDEO): Сгенерированное видео
- `last_frame` (IMAGE): Последний кадр
- `frames` (IMAGE): Все кадры видео
- `audio` (AUDIO): Аудио из видео (если есть)

**Configuration:**
- API key: через `agnes_config.json` или панель настроек
- Base URL: https://api.agnes.ai/v1
- Timeout: system default

**Related:** AgnesImage, AgnesText

---

### AlignYourStepsScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### AnimaLLLiteApply

- **Category:** model_patches/anima
- **Documented:** No

---

### ApplyTextureToMesh

- **Category:** 3d/texturing
- **Documented:** No

---

### Audio To Blob Node

- **Category:** RequestNode/Converters
- **Documented:** Yes

**Purpose:** Конвертирует ComfyUI AUDIO → байты WAV

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| audio | AUDIO |  | Аудио ComfyUI |

**Outputs:**
- `wav_bytes` (BYTES): Байты WAV

**Related:** Blob To Audio Node, Base64 To Audio Node

---

### AudioAdjustVolume

- **Category:** audio
- **Documented:** No

---

### AudioConcat

- **Category:** audio
- **Documented:** No

---

### AudioEncoderEncode

- **Category:** model/conditioning
- **Documented:** No

---

### AudioEncoderLoader

- **Category:** model/loaders
- **Documented:** No

---

### AudioEqualizer3Band

- **Category:** audio
- **Documented:** No

---

### AudioMerge

- **Category:** audio
- **Documented:** No

---

### BakeAmbientOcclusion

- **Category:** 3d/texturing
- **Documented:** No

---

### BakeNormalMapFromMesh

- **Category:** 3d/texturing
- **Documented:** No

---

### BakeTextureFromVoxel

- **Category:** 3d/texturing
- **Documented:** No

---

### Base64 To Audio Node

- **Category:** RequestNode/Converters
- **Documented:** Yes

**Purpose:** Конвертирует Base64 строку → ComfyUI AUDIO

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| base64_string | STRING |  | Base64 строка WAV |

**Outputs:**
- `audio` (AUDIO): Аудио ComfyUI

**Related:** Audio To Blob Node, Blob To Audio Node

---

### BasicGuider

- **Category:** model/sampling/guiders
- **Documented:** No

---

### BasicScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### BatchImagesNode

- **Category:** image/batch
- **Documented:** No

---

### BatchLatentsNode

- **Category:** model/latent/batch
- **Documented:** No

---

### BatchMasksNode

- **Category:** image/mask
- **Documented:** No

---

### BeebleSwitchXImageEdit

- **Category:** partner/image/Beeble
- **Documented:** No

---

### BeebleSwitchXVideoEdit

- **Category:** partner/video/Beeble
- **Documented:** No

---

### BerniniConditioning

- **Category:** model/conditioning/bernini
- **Documented:** No

---

### BetaSamplingScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### Binary Post Request Node

- **Category:** RequestNode/REST API
- **Documented:** Yes

**Purpose:** Отправка сырых байтов (application/octet-stream)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| target_url | STRING | http://127.0.0.1:8000/rvc/default | URL для запроса |
| body | BYTES |  | Данные для отправки |

**Outputs:**
- `text` (STRING): Ответ как текст
- `response_bytes` (BYTES): Ответ как байты
- `json` (JSON): Ответ как JSON
- `status_code` (INT): HTTP статус код
- `response_headers` (DICT): Заголовки ответа

**Related:** Media Form Post Node, Rest Api Node

---

### Blob To Audio Node

- **Category:** RequestNode/Utils
- **Documented:** Yes

**Purpose:** Конвертирует байты WAV → ComfyUI AUDIO

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| bytes | BYTES |  | Байты WAV |

**Outputs:**
- `audio` (AUDIO): Аудио ComfyUI {"waveform": [batch, channels, samples], "sample_rate": int}

**Related:** Audio To Blob Node, Base64 To Audio Node

---

### Blob To Batch Image Node

- **Category:** RequestNode/Utils
- **Documented:** Yes

**Purpose:** Конвертирует байты → ComfyUI IMAGE (поддержка multi-page TIFF)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| bytes | BYTES |  | Байты изображения |

**Outputs:**
- `images` (IMAGE): Изображение ComfyUI

**Related:** Blob To Image Node

---

### Blob To Image Node

- **Category:** RequestNode/Utils
- **Documented:** Yes

**Purpose:** Конвертирует байты (PNG/JPEG/BMP/WebP) → ComfyUI IMAGE

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| bytes | BYTES |  | Байты изображения |

**Outputs:**
- `image` (IMAGE): Изображение ComfyUI [batch, height, width, channels]

**Related:** Image To Blob Node, Blob To Batch Image Node

---

### Blob To Video Node

- **Category:** RequestNode/Utils
- **Documented:** Yes

**Purpose:** Конвертирует байты видео (MP4/GIF/WebM) → ComfyUI VIDEO

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| bytes | BYTES |  | Байты видео |

**Outputs:**
- `video` (VIDEO): Видео ComfyUI (совместимо с VHS нодами)

**Related:** Video To Blob Node

---

### BriaEraser

- **Category:** partner/image/Bria
- **Documented:** No

---

### BriaExpandImage

- **Category:** partner/image/Bria
- **Documented:** No

---

### BriaGenFill

- **Category:** partner/image/Bria
- **Documented:** No

---

### BriaImageEditNode

- **Category:** partner/image/Bria
- **Documented:** No

---

### BriaIncreaseResolution

- **Category:** partner/image/Bria
- **Documented:** No

---

### BriaRemoveImageBackground

- **Category:** partner/image/Bria
- **Documented:** No

---

### BriaRemoveVideoBackground

- **Category:** partner/video/Bria
- **Documented:** No

---

### BriaTransparentVideoBackground

- **Category:** partner/video/Bria
- **Documented:** No

---

### BriaVideoGreenScreen

- **Category:** partner/video/Bria
- **Documented:** No

---

### BriaVideoReplaceBackground

- **Category:** partner/video/Bria
- **Documented:** No

---

### BuildJsonPromptIdeogram

- **Category:** text
- **Documented:** No

---

### BuildPoseFile

- **Category:** 3d
- **Documented:** No

---

### ByteDance2FirstLastFrameNode

- **Category:** partner/video/ByteDance
- **Documented:** No

---

### ByteDance2ReferenceNode

- **Category:** partner/video/ByteDance
- **Documented:** No

---

### ByteDance2ReferenceNodeV2

- **Category:** partner/video/ByteDance
- **Documented:** No

---

### ByteDance2TextToVideoNode

- **Category:** partner/video/ByteDance
- **Documented:** No

---

### ByteDanceCreateImageAsset

- **Category:** partner/image/ByteDance
- **Documented:** No

---

### ByteDanceCreateVideoAsset

- **Category:** partner/video/ByteDance
- **Documented:** No

---

### ByteDanceFirstLastFrameNode

- **Category:** partner/video/ByteDance
- **Documented:** No

---

### ByteDanceImageNode

- **Category:** partner/image/ByteDance
- **Documented:** No

---

### ByteDanceImageReferenceNode

- **Category:** partner/video/ByteDance
- **Documented:** No

---

### ByteDanceImageToVideoNode

- **Category:** partner/video/ByteDance
- **Documented:** No

---

### ByteDanceSeedAudio

- **Category:** partner/audio/ByteDance
- **Documented:** No

---

### ByteDanceSeedNode

- **Category:** partner/text/ByteDance
- **Documented:** No

---

### ByteDanceSeedreamLayerSeparationNode

- **Category:** partner/image/ByteDance
- **Documented:** No

---

### ByteDanceSeedreamNode

- **Category:** partner/image/ByteDance
- **Documented:** No

---

### ByteDanceSeedreamNodeV2

- **Category:** partner/image/ByteDance
- **Documented:** No

---

### ByteDanceSeedreamNodeV3

- **Category:** partner/image/ByteDance
- **Documented:** No

---

### ByteDanceTextToVideoNode

- **Category:** partner/video/ByteDance
- **Documented:** No

---

### ByteDanceVideoEnhanceNode

- **Category:** partner/video/ByteDance
- **Documented:** No

---

### CFGGuider

- **Category:** model/sampling/guiders
- **Documented:** No

---

### CFGNorm

- **Category:** advanced/guidance
- **Documented:** No

---

### CFGOverride

- **Category:** model/sampling/guiders
- **Documented:** No

---

### CFGZeroStar

- **Category:** advanced/guidance
- **Documented:** No

---

### CLIPAttentionMultiply

- **Category:** experimental/attention_experiments
- **Documented:** No

---

### CLIPLoader

- **Category:** model/loaders
- **Documented:** No

---

### CLIPMergeAdd

- **Category:** model/merging
- **Documented:** No

---

### CLIPMergeSimple

- **Category:** model/merging
- **Documented:** No

---

### CLIPMergeSubtract

- **Category:** model/merging
- **Documented:** No

---

### CLIPSave

- **Category:** model/merging
- **Documented:** No

---

### CLIPSetLastLayer

- **Category:** model/conditioning
- **Documented:** No

---

### CLIPTextEncode

- **Category:** model/conditioning
- **Documented:** No

---

### CLIPTextEncodeControlnet

- **Category:** model/conditioning
- **Documented:** No

---

### CLIPTextEncodeFlux

- **Category:** model/conditioning/flux
- **Documented:** No

---

### CLIPTextEncodeHiDream

- **Category:** model/conditioning/hidream
- **Documented:** No

---

### CLIPTextEncodeHunyuanDiT

- **Category:** model/conditioning/hunyuan image
- **Documented:** No

---

### CLIPTextEncodeKandinsky5

- **Category:** model/conditioning/kandinsky
- **Documented:** No

---

### CLIPTextEncodeLumina2

- **Category:** model/conditioning/lumina
- **Documented:** No

---

### CLIPTextEncodePixArtAlpha

- **Category:** model/conditioning/pixart
- **Documented:** No

---

### CLIPTextEncodeSD3

- **Category:** model/conditioning/stable diffusion
- **Documented:** No

---

### CLIPTextEncodeSDXL

- **Category:** model/conditioning/stable diffusion
- **Documented:** No

---

### CLIPTextEncodeSDXLRefiner

- **Category:** model/conditioning/stable diffusion
- **Documented:** No

---

### CLIPVisionEncode

- **Category:** model/conditioning
- **Documented:** No

---

### CLIPVisionLoader

- **Category:** model/loaders
- **Documented:** No

---

### Canny

- **Category:** image/filters
- **Documented:** No

---

### CaseConverter

- **Category:** text
- **Documented:** No

---

### CenterCropImages

- **Category:** image/transform
- **Documented:** No

---

### Chainable Upload Image

- **Category:** RequestNode/Utils
- **Documented:** Yes

**Purpose:** Объединяет изображения в батч для отправки

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| image | IMAGE |  | Изображение ComfyUI |

**Outputs:**
- `image_batch_out` (IMAGE): Батч изображений

**Related:** Image To Blob Node, Media Form Post Node

---

### CheckpointLoader

- **Category:** model/loaders
- **Documented:** No

---

### CheckpointLoaderSimple

- **Category:** model/loaders
- **Documented:** No

---

### CheckpointSave

- **Category:** model/merging
- **Documented:** No

---

### ChromaRadianceOptions

- **Category:** model/patch/chroma radiance
- **Documented:** No

---

### ClaudeNode

- **Category:** partner/text/Anthropic
- **Documented:** No

---

### ColorToRGBInt

- **Category:** utilities
- **Documented:** No

---

### ColorTransfer

- **Category:** image/filters
- **Documented:** No

---

### CombineHooks2

- **Category:** advanced/hooks/combine
- **Documented:** No

---

### CombineHooks4

- **Category:** advanced/hooks/combine
- **Documented:** No

---

### CombineHooks8

- **Category:** advanced/hooks/combine
- **Documented:** No

---

### ComfyAndNode

- **Category:** utilities/logic
- **Documented:** No

---

### ComfyCloudFlux2TextToImageNode

- **Category:** comfy cloud/image
- **Documented:** No

---

### ComfyCloudMageFlowTextToImageNode

- **Category:** comfy cloud/image
- **Documented:** No

---

### ComfyCloudMageFlowTurboTextToImageNode

- **Category:** comfy cloud/image
- **Documented:** No

---

### ComfyCloudMiniMaxH3FirstLastFrameToVideoNode

- **Category:** comfy cloud/video
- **Documented:** No

---

### ComfyCloudMiniMaxH3ImageToVideoNode

- **Category:** comfy cloud/video
- **Documented:** No

---

### ComfyCloudMiniMaxH3TextToVideoNode

- **Category:** comfy cloud/video
- **Documented:** No

---

### ComfyCloudMiniMaxMusic3TextToAudioNode

- **Category:** comfy cloud/audio
- **Documented:** No

---

### ComfyCloudZImageTurboNode

- **Category:** comfy cloud/image
- **Documented:** No

---

### ComfyMathExpression

- **Category:** utilities
- **Documented:** No

---

### ComfyNotNode

- **Category:** utilities/logic
- **Documented:** No

---

### ComfyNumberConvert

- **Category:** utilities
- **Documented:** No

---

### ComfyOrNode

- **Category:** utilities/logic
- **Documented:** No

---

### ComfySwitchNode

- **Category:** utilities/logic
- **Documented:** No

---

### ConditioningAverage

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ConditioningCombine

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ConditioningConcat

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ConditioningMultiply

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ConditioningSetArea

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ConditioningSetAreaPercentage

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ConditioningSetAreaPercentageVideo

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ConditioningSetAreaStrength

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ConditioningSetDefaultCombine

- **Category:** advanced/hooks/cond single
- **Documented:** No

---

### ConditioningSetMask

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ConditioningSetProperties

- **Category:** advanced/hooks/cond single
- **Documented:** No

---

### ConditioningSetPropertiesAndCombine

- **Category:** advanced/hooks/cond single
- **Documented:** No

---

### ConditioningSetTimestepRange

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ConditioningStableAudio

- **Category:** model/conditioning/stable audio
- **Documented:** No

---

### ConditioningTimestepsRange

- **Category:** advanced/hooks
- **Documented:** No

---

### ConditioningZeroOut

- **Category:** model/conditioning/transform
- **Documented:** No

---

### ContextWindowsManual

- **Category:** model/patch
- **Documented:** No

---

### ControlNetApply

- **Category:** model/conditioning/controlnet
- **Documented:** No

---

### ControlNetApplyAdvanced

- **Category:** model/conditioning/controlnet
- **Documented:** No

---

### ControlNetApplySD3

- **Category:** model/conditioning/controlnet
- **Documented:** No

---

### ControlNetInpaintingAliMamaApply

- **Category:** model/conditioning/controlnet
- **Documented:** No

---

### ControlNetLoader

- **Category:** model/loaders
- **Documented:** No

---

### ConvertArrayToString

- **Category:** text
- **Documented:** No

---

### ConvertDictionaryToString

- **Category:** text
- **Documented:** No

---

### CosmosImageToVideoLatent

- **Category:** model/conditioning/cosmos
- **Documented:** No

---

### CosmosPredict2ImageToVideoLatent

- **Category:** model/conditioning/cosmos
- **Documented:** No

---

### CreateBoundingBoxes

- **Category:** utilities
- **Documented:** No

---

### CreateCameraInfo

- **Category:** 3d
- **Documented:** No

---

### CreateHookKeyframe

- **Category:** advanced/hooks/scheduling
- **Documented:** No

---

### CreateHookKeyframesFromFloats

- **Category:** advanced/hooks/scheduling
- **Documented:** No

---

### CreateHookKeyframesInterpolated

- **Category:** advanced/hooks/scheduling
- **Documented:** No

---

### CreateHookLora

- **Category:** advanced/hooks/create
- **Documented:** No

---

### CreateHookLoraModelOnly

- **Category:** advanced/hooks/create
- **Documented:** No

---

### CreateHookModelAsLora

- **Category:** advanced/hooks/create
- **Documented:** No

---

### CreateHookModelAsLoraModelOnly

- **Category:** advanced/hooks/create
- **Documented:** No

---

### CreateList

- **Category:** utilities
- **Documented:** No

---

### CreateVideo

- **Category:** video
- **Documented:** No

---

### CropByBBoxes

- **Category:** image/transform
- **Documented:** No

---

### CropMask

- **Category:** image/mask
- **Documented:** No

---

### CurveEditor

- **Category:** utilities
- **Documented:** No

---

### CustomCombo

- **Category:** utilities
- **Documented:** No

---

### DA3GeometryToMesh

- **Category:** image/geometry estimation
- **Documented:** No

---

### DA3Inference

- **Category:** image/geometry estimation
- **Documented:** No

---

### DA3Render

- **Category:** image/geometry estimation
- **Documented:** No

---

### DecimateMesh

- **Category:** 3d/mesh
- **Documented:** No

---

### DiffControlNetLoader

- **Category:** model/loaders
- **Documented:** No

---

### DifferentialDiffusion

- **Category:** experimental
- **Documented:** No

---

### DiffusersLoader

- **Category:** model/loaders
- **Documented:** No

---

### DisableNoise

- **Category:** model/sampling/noise
- **Documented:** No

---

### DrawBBoxes

- **Category:** image/detection
- **Documented:** No

---

### DualCFGGuider

- **Category:** model/sampling/guiders
- **Documented:** No

---

### DualCLIPLoader

- **Category:** model/loaders
- **Documented:** No

---

### DualModelGuider

- **Category:** model/sampling/guiders
- **Documented:** No

---

### EasyCache

- **Category:** advanced/debug
- **Documented:** No

---

### ElevenLabsAudioIsolation

- **Category:** partner/audio/ElevenLabs
- **Documented:** No

---

### ElevenLabsInstantVoiceClone

- **Category:** partner/audio/ElevenLabs
- **Documented:** No

---

### ElevenLabsSpeechToSpeech

- **Category:** partner/audio/ElevenLabs
- **Documented:** No

---

### ElevenLabsSpeechToText

- **Category:** partner/audio/ElevenLabs
- **Documented:** No

---

### ElevenLabsTextToDialogue

- **Category:** partner/audio/ElevenLabs
- **Documented:** No

---

### ElevenLabsTextToSoundEffects

- **Category:** partner/audio/ElevenLabs
- **Documented:** No

---

### ElevenLabsTextToSpeech

- **Category:** partner/audio/ElevenLabs
- **Documented:** No

---

### ElevenLabsVoiceSelector

- **Category:** partner/audio/ElevenLabs
- **Documented:** No

---

### EmptyARVideoLatent

- **Category:** model/latent/autoregressive
- **Documented:** No

---

### EmptyAceStep1.5LatentAudio

- **Category:** model/latent/ace
- **Documented:** No

---

### EmptyAceStepLatentAudio

- **Category:** model/latent/ace
- **Documented:** No

---

### EmptyAudio

- **Category:** audio
- **Documented:** No

---

### EmptyChromaRadianceLatentImage

- **Category:** model/latent/chroma radiance
- **Documented:** No

---

### EmptyCosmosLatentVideo

- **Category:** model/latent/cosmos
- **Documented:** No

---

### EmptyFlux2LatentImage

- **Category:** model/latent/flux
- **Documented:** No

---

### EmptyHiDreamO1LatentImage

- **Category:** model/latent/hidream
- **Documented:** No

---

### EmptyHunyuanImageLatent

- **Category:** model/latent/hunyuan image
- **Documented:** No

---

### EmptyHunyuanLatentVideo

- **Category:** model/latent/hunyuan video
- **Documented:** No

---

### EmptyHunyuanVideo15Latent

- **Category:** model/latent/hunyuan video
- **Documented:** No

---

### EmptyImage

- **Category:** image
- **Documented:** No

---

### EmptyLTXVLatentVideo

- **Category:** model/latent/ltxv
- **Documented:** No

---

### EmptyLatentAudio

- **Category:** model/latent
- **Documented:** No

---

### EmptyLatentHunyuan3Dv2

- **Category:** model/latent/hunyuan 3d
- **Documented:** No

---

### EmptyLatentImage

- **Category:** model/latent
- **Documented:** No

---

### EmptyMiniMaxH3LatentAV

- **Category:** model/latent/minimax
- **Documented:** No

---

### EmptyMiniMaxMusic3LatentAudio

- **Category:** model/latent/minimax music
- **Documented:** No

---

### EmptyMochiLatentVideo

- **Category:** model/latent/mochi
- **Documented:** No

---

### EmptyQwenImageLayeredLatentImage

- **Category:** model/latent/qwen
- **Documented:** No

---

### EmptySD3LatentImage

- **Category:** model/latent/stable diffusion
- **Documented:** No

---

### EmptyTrellis2LatentStructure

- **Category:** model/latent/trellis
- **Documented:** No

---

### Epsilon Scaling

- **Category:** model/patch/unet
- **Documented:** No

---

### ExponentialScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### ExtendIntermediateSigmas

- **Category:** model/sampling/sigmas
- **Documented:** No

---

### FeatherMask

- **Category:** image/mask
- **Documented:** No

---

### File3DToSplat

- **Category:** 3d/splat
- **Documented:** No

---

### FillHoles

- **Category:** 3d/mesh
- **Documented:** No

---

### FishAudioInstantVoiceClone

- **Category:** partner/audio/Fish Audio
- **Documented:** No

---

### FishAudioSpeechToText

- **Category:** partner/audio/Fish Audio
- **Documented:** No

---

### FishAudioTextToSpeech

- **Category:** partner/audio/Fish Audio
- **Documented:** No

---

### FishAudioVoiceSelector

- **Category:** partner/audio/Fish Audio
- **Documented:** No

---

### FlipSigmas

- **Category:** model/sampling/sigmas
- **Documented:** No

---

### Flux2ImageNode

- **Category:** partner/image/BFL
- **Documented:** No

---

### Flux2MaxImageNode

- **Category:** partner/image/BFL
- **Documented:** No

---

### Flux2ProImageNode

- **Category:** partner/image/BFL
- **Documented:** No

---

### Flux2Scheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### Flux3ImageToVideoNode

- **Category:** partner/video/BFL
- **Documented:** No

---

### Flux3TextToVideoNode

- **Category:** partner/video/BFL
- **Documented:** No

---

### Flux3VideoContinuationNode

- **Category:** partner/video/BFL
- **Documented:** No

---

### FluxDisableGuidance

- **Category:** model/conditioning/flux
- **Documented:** No

---

### FluxEraseNode

- **Category:** partner/image/BFL
- **Documented:** No

---

### FluxGuidance

- **Category:** model/conditioning/flux
- **Documented:** No

---

### FluxKVCache

- **Category:** experimental
- **Documented:** No

---

### FluxKontextImageScale

- **Category:** model/conditioning/flux
- **Documented:** No

---

### FluxKontextMaxImageNode

- **Category:** partner/image/BFL
- **Documented:** No

---

### FluxKontextMultiReferenceLatentMethod

- **Category:** model/conditioning/flux
- **Documented:** No

---

### FluxKontextProImageNode

- **Category:** partner/image/BFL
- **Documented:** No

---

### FluxProExpandNode

- **Category:** partner/image/BFL
- **Documented:** No

---

### FluxProFillNode

- **Category:** partner/image/BFL
- **Documented:** No

---

### FluxProUltraImageNode

- **Category:** partner/image/BFL
- **Documented:** No

---

### FluxVTONode

- **Category:** partner/image/BFL
- **Documented:** No

---

### FluxVideoUpscaleNode

- **Category:** partner/video/BFL
- **Documented:** No

---

### Form Post Request Node

- **Category:** RequestNode/Post Request
- **Documented:** Yes

**Purpose:** HTTP POST запрос с form-data (multipart)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| target_url | STRING | http://127.0.0.1:7788/api/echo | URL для запроса |
| image | IMAGE |  |  |
| image_field_name | STRING | image |  |

**Outputs:**
- `text` (STRING): Ответ как текст
- `json` (JSON): Ответ как JSON
- `any` (ANY): Ответ как байты

**Related:** Post Request Node, Media Form Post Node

---

### FrameInterpolate

- **Category:** video
- **Documented:** No

---

### FrameInterpolationModelLoader

- **Category:** model/loaders
- **Documented:** No

---

### FreSca

- **Category:** experimental
- **Documented:** No

---

### FreeU

- **Category:** model/patch/unet
- **Documented:** No

---

### FreeU_V2

- **Category:** model/patch/unet
- **Documented:** No

---

### GITSScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### GLIGENLoader

- **Category:** model/loaders
- **Documented:** No

---

### GLIGENTextBoxApply

- **Category:** model/conditioning/gligen
- **Documented:** No

---

### GLSLShader

- **Category:** image/shader
- **Documented:** No

---

### GeminiImage2Node

- **Category:** partner/image/Gemini
- **Documented:** No

---

### GeminiImageNode

- **Category:** partner/image/Gemini
- **Documented:** No

---

### GeminiInputFiles

- **Category:** partner/text/Gemini
- **Documented:** No

---

### GeminiNanoBanana2

- **Category:** partner/image/Gemini
- **Documented:** No

---

### GeminiNanoBanana2V2

- **Category:** partner/image/Gemini
- **Documented:** No

---

### GeminiNode

- **Category:** partner/text/Gemini
- **Documented:** No

---

### GeminiNodeV2

- **Category:** partner/text/Gemini
- **Documented:** No

---

### GeminiVideoOmni

- **Category:** partner/video/Gemini
- **Documented:** No

---

### GeminiVideoOmniV2

- **Category:** partner/video/Gemini
- **Documented:** No

---

### GenerateTracks

- **Category:** model/conditioning/wan/move
- **Documented:** No

---

### Get Request Node

- **Category:** RequestNode/Get Request
- **Documented:** Yes

**Purpose:** HTTP GET запрос

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| target_url | STRING | https://example.com/api | URL для запроса |

**Outputs:**
- `text` (STRING): Ответ как текст
- `file` (BYTES): Ответ как байты
- `json` (JSON): Ответ как JSON
- `any` (ANY): Ответ как байты

**Configuration:**
- proxy: Не используется (proxies={http:None, https:None})
- timeout: System default
- retry: Настраивается через Retry Settings Node

**Related:** Post Request Node, Rest Api Node, KeyValueNode

---

### GetICLoRAParameters

- **Category:** model/conditioning/ltxv
- **Documented:** No

---

### GetImageSize

- **Category:** image
- **Documented:** No

---

### GetMeshInfo

- **Category:** 3d/mesh
- **Documented:** No

---

### GetSplatCount

- **Category:** 3d/splat
- **Documented:** No

---

### GetVideoComponents

- **Category:** video
- **Documented:** No

---

### GrokImageEditNode

- **Category:** partner/image/Grok
- **Documented:** No

---

### GrokImageEditNodeV2

- **Category:** partner/image/Grok
- **Documented:** No

---

### GrokImageNode

- **Category:** partner/image/Grok
- **Documented:** No

---

### GrokVideoEditNode

- **Category:** partner/video/Grok
- **Documented:** No

---

### GrokVideoExtendNode

- **Category:** partner/video/Grok
- **Documented:** No

---

### GrokVideoNode

- **Category:** partner/video/Grok
- **Documented:** No

---

### GrokVideoReferenceNode

- **Category:** partner/video/Grok
- **Documented:** No

---

### GrowMask

- **Category:** image/mask
- **Documented:** No

---

### HappyHorseImageToVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### HappyHorseReferenceVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### HappyHorseTextToVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### HappyHorseVideoEditApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### HeyGenAvatarVideoNode

- **Category:** partner/video/HeyGen
- **Documented:** No

---

### HeyGenCreateAvatarNode

- **Category:** partner/video/HeyGen
- **Documented:** No

---

### HeyGenTalkingPhotoNode

- **Category:** partner/video/HeyGen
- **Documented:** No

---

### HeyGenTextToSpeechNode

- **Category:** partner/audio/HeyGen
- **Documented:** No

---

### HeyGenVideoTranslateNode

- **Category:** partner/video/HeyGen
- **Documented:** No

---

### HiDreamO1PatchSeamSmoothing

- **Category:** model/patch/hidream
- **Documented:** No

---

### HiDreamO1ReferenceImages

- **Category:** model/conditioning/hidream
- **Documented:** No

---

### HitPawGeneralImageEnhance

- **Category:** partner/image/HitPaw
- **Documented:** No

---

### HitPawVideoEnhance

- **Category:** partner/video/HitPaw
- **Documented:** No

---

### Hunyuan3Dv2Conditioning

- **Category:** model/conditioning/hunyuan 3d
- **Documented:** No

---

### Hunyuan3Dv2ConditioningMultiView

- **Category:** model/conditioning/hunyuan 3d
- **Documented:** No

---

### HunyuanImageToVideo

- **Category:** model/conditioning/hunyuan video
- **Documented:** No

---

### HunyuanRefinerLatent

- **Category:** model/conditioning/hunyuan video
- **Documented:** No

---

### HunyuanVideo15ImageToVideo

- **Category:** model/conditioning/hunyuan video
- **Documented:** No

---

### HunyuanVideo15LatentUpscaleWithModel

- **Category:** model/latent/hunyhuan video
- **Documented:** No

---

### HunyuanVideo15SuperResolution

- **Category:** model/conditioning/hunyuan video
- **Documented:** No

---

### HyperTile

- **Category:** model/patch/unet
- **Documented:** No

---

### HypernetworkLoader

- **Category:** model/loaders
- **Documented:** No

---

### Ideogram4Scheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### IdeogramPImage

- **Category:** partner/image/Ideogram
- **Documented:** No

---

### IdeogramV3

- **Category:** partner/image/Ideogram
- **Documented:** No

---

### IdeogramV4

- **Category:** partner/image/Ideogram
- **Documented:** No

---

### Image To Base64 Node

- **Category:** RequestNode/Converters
- **Documented:** Yes

**Purpose:** Конвертирует ComfyUI IMAGE → Base64 строку

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| image | IMAGE |  | Изображение ComfyUI |

**Outputs:**
- `STRING` (STRING): 

**Related:** Image To Blob Node, Blob To Image Node

---

### Image To Blob Node

- **Category:** RequestNode/Converters
- **Documented:** Yes

**Purpose:** Конвертирует ComfyUI IMAGE → байты (PNG)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| image | IMAGE |  | Изображение ComfyUI |

**Outputs:**
- `BYTES` (BYTES): 

**Related:** Image To Base64 Node, Blob To Image Node

---

### ImageAddNoise

- **Category:** image/filters
- **Documented:** No

---

### ImageBatch

- **Category:** image/batch
- **Documented:** No

---

### ImageBlend

- **Category:** image/filters
- **Documented:** No

---

### ImageBlur

- **Category:** image/filters
- **Documented:** No

---

### ImageColorToMask

- **Category:** image/mask
- **Documented:** No

---

### ImageCompare

- **Category:** image
- **Documented:** No

---

### ImageCompositeMasked

- **Category:** image/compositing
- **Documented:** No

---

### ImageCompositor

- **Category:** image
- **Documented:** No

---

### ImageCrop

- **Category:** image/transform
- **Documented:** No

---

### ImageCropToMask

- **Category:** image/transform
- **Documented:** No

---

### ImageCropV2

- **Category:** image/transform
- **Documented:** No

---

### ImageDeduplication

- **Category:** image/batch
- **Documented:** No

---

### ImageFlip

- **Category:** image/transform
- **Documented:** No

---

### ImageFromBatch

- **Category:** image/batch
- **Documented:** No

---

### ImageGrid

- **Category:** image/batch
- **Documented:** No

---

### ImageHistogram

- **Category:** utilities
- **Documented:** No

---

### ImageInvert

- **Category:** image/color
- **Documented:** No

---

### ImageMergeTileList

- **Category:** image/batch
- **Documented:** No

---

### ImageOnlyCheckpointLoader

- **Category:** model/loaders
- **Documented:** No

---

### ImageOnlyCheckpointSave

- **Category:** model/merging
- **Documented:** No

---

### ImagePadForOutpaint

- **Category:** image/transform
- **Documented:** No

---

### ImageQuantize

- **Category:** image/filters
- **Documented:** No

---

### ImageRGBA2RGB

- **Category:** 🌌 ReActor
- **Documented:** Yes

**Purpose:** Конвертация RGBA → RGB

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| image | IMAGE |  | RGBA изображение |

**Outputs:**
- `IMAGE` (IMAGE): RGB изображение

---

### ImageRGBToYUV

- **Category:** image/color
- **Documented:** No

---

### ImageRotate

- **Category:** image/transform
- **Documented:** No

---

### ImageScale

- **Category:** image/upscaling
- **Documented:** No

---

### ImageScaleBy

- **Category:** image/upscaling
- **Documented:** No

---

### ImageScaleToMaxDimension

- **Category:** image/upscaling
- **Documented:** No

---

### ImageScaleToTotalPixels

- **Category:** image/upscaling
- **Documented:** No

---

### ImageSharpen

- **Category:** image/filters
- **Documented:** No

---

### ImageStitch

- **Category:** image/transform
- **Documented:** No

---

### ImageToMask

- **Category:** image/mask
- **Documented:** No

---

### ImageUpscaleWithModel

- **Category:** image/upscaling
- **Documented:** No

---

### ImageYUVToRGB

- **Category:** image/color
- **Documented:** No

---

### InpaintModelConditioning

- **Category:** model/conditioning
- **Documented:** No

---

### InstructPixToPixConditioning

- **Category:** model/conditioning/instructpix2pix
- **Documented:** No

---

### InvertMask

- **Category:** image/mask
- **Documented:** No

---

### JoinAudioChannels

- **Category:** audio
- **Documented:** No

---

### JoinImageWithAlpha

- **Category:** image/compositing
- **Documented:** No

---

### JsonExtractString

- **Category:** text
- **Documented:** No

---

### KSampler

- **Category:** model/sampling
- **Documented:** No

---

### KSamplerAdvanced

- **Category:** model/sampling
- **Documented:** No

---

### KSamplerSelect

- **Category:** model/sampling/samplers
- **Documented:** No

---

### Kandinsky5ImageToVideo

- **Category:** model/conditioning/kandinsky
- **Documented:** No

---

### KarrasScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### Key/Value Node

- **Category:** RequestNode/KeyValue
- **Documented:** Yes

**Purpose:** Создаёт пары ключ-значение для HTTP заголовков и параметров

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| key | STRING |  | Ключ |
| value | STRING |  | Значение |

**Outputs:**
- `KEY_VALUE` (KEY_VALUE): Пара ключ-значение

**Related:** Get Request Node, Post Request Node, Rest Api Node

---

### KlingAvatarNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingFirstLastFrameNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingImage2VideoNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingImageGenerationNode

- **Category:** partner/image/Kling
- **Documented:** No

---

### KlingImageToVideoWithAudio

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingLipSyncAudioToVideoNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingLipSyncTextToVideoNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingMotionControl

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingOmniProEditVideoNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingOmniProFirstLastFrameNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingOmniProImageNode

- **Category:** partner/image/Kling
- **Documented:** No

---

### KlingOmniProImageToVideoNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingOmniProTextToVideoNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingOmniProVideoToVideoNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingStartEndFrameNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingTextToVideoNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingTextToVideoWithAudio

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingVideoExtendNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### KlingVideoNode

- **Category:** partner/video/Kling
- **Documented:** No

---

### Krea2ImageNode

- **Category:** partner/image/Krea
- **Documented:** No

---

### Krea2StyleReferenceNode

- **Category:** partner/image/Krea
- **Documented:** No

---

### LTXAVTextEncoderLoader

- **Category:** model/loaders
- **Documented:** No

---

### LTXVAddGuide

- **Category:** model/conditioning/ltxv
- **Documented:** No

---

### LTXVAudioVAEDecode

- **Category:** model/latent/ltxv
- **Documented:** No

---

### LTXVAudioVAEEncode

- **Category:** model/latent/ltxv
- **Documented:** No

---

### LTXVAudioVAELoader

- **Category:** model/loaders
- **Documented:** No

---

### LTXVConcatAVLatent

- **Category:** model/latent/ltxv
- **Documented:** No

---

### LTXVConditioning

- **Category:** model/conditioning/ltxv
- **Documented:** No

---

### LTXVContextWindows

- **Category:** model/patch
- **Documented:** No

---

### LTXVCropGuides

- **Category:** model/conditioning/ltxv
- **Documented:** No

---

### LTXVDualCFGGuider

- **Category:** model/sampling/guiders
- **Documented:** No

---

### LTXVDurationPredictor

- **Category:** conditioning/video_models
- **Documented:** No

---

### LTXVEmptyLatentAudio

- **Category:** model/latent/ltxv
- **Documented:** No

---

### LTXVImgToVideo

- **Category:** model/conditioning/ltxv
- **Documented:** No

---

### LTXVImgToVideoInplace

- **Category:** model/conditioning/ltxv
- **Documented:** No

---

### LTXVLatentUpsampler

- **Category:** model/latent/ltxv
- **Documented:** No

---

### LTXVModalityGuidance

- **Category:** advanced/guidance
- **Documented:** No

---

### LTXVPreprocess

- **Category:** video/preprocessors
- **Documented:** No

---

### LTXVReferenceAudio

- **Category:** model/conditioning/ltxv
- **Documented:** No

---

### LTXVScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### LTXVSeparateAVLatent

- **Category:** model/latent/ltxv
- **Documented:** No

---

### LTXVSpatioTemporalGuidance

- **Category:** advanced/guidance
- **Documented:** No

---

### LaplaceScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### LatentAdd

- **Category:** model/latent/advanced
- **Documented:** No

---

### LatentApplyOperation

- **Category:** model/latent/advanced/operations
- **Documented:** No

---

### LatentApplyOperationCFG

- **Category:** model/latent/advanced/operations
- **Documented:** No

---

### LatentBatch

- **Category:** model/latent/batch
- **Documented:** No

---

### LatentBatchSeedBehavior

- **Category:** model/latent/advanced
- **Documented:** No

---

### LatentBlend

- **Category:** experimental
- **Documented:** No

---

### LatentComposite

- **Category:** model/latent
- **Documented:** No

---

### LatentCompositeMasked

- **Category:** model/latent
- **Documented:** No

---

### LatentConcat

- **Category:** model/latent/advanced
- **Documented:** No

---

### LatentCrop

- **Category:** model/latent/transform
- **Documented:** No

---

### LatentCut

- **Category:** model/latent/advanced
- **Documented:** No

---

### LatentCutToBatch

- **Category:** model/latent/advanced
- **Documented:** No

---

### LatentFlip

- **Category:** model/latent/transform
- **Documented:** No

---

### LatentFromBatch

- **Category:** model/latent/batch
- **Documented:** No

---

### LatentInterpolate

- **Category:** model/latent/advanced
- **Documented:** No

---

### LatentMultiply

- **Category:** model/latent/advanced
- **Documented:** No

---

### LatentOperationSharpen

- **Category:** model/latent/advanced/operations
- **Documented:** No

---

### LatentOperationTonemapReinhard

- **Category:** model/latent/advanced/operations
- **Documented:** No

---

### LatentRotate

- **Category:** model/latent/transform
- **Documented:** No

---

### LatentSubtract

- **Category:** model/latent/advanced
- **Documented:** No

---

### LatentUpscale

- **Category:** model/latent
- **Documented:** No

---

### LatentUpscaleBy

- **Category:** model/latent
- **Documented:** No

---

### LatentUpscaleModelLoader

- **Category:** model/loaders
- **Documented:** No

---

### LayersFromBoundingBoxes

- **Category:** image
- **Documented:** No

---

### LazyCache

- **Category:** advanced/debug
- **Documented:** No

---

### Load3D

- **Category:** 3d
- **Documented:** No

---

### Load3DAdvanced

- **Category:** 3d
- **Documented:** No

---

### LoadAudio

- **Category:** audio
- **Documented:** No

---

### LoadBackgroundRemovalModel

- **Category:** model/loaders
- **Documented:** No

---

### LoadDA3Model

- **Category:** model/loaders
- **Documented:** No

---

### LoadImage

- **Category:** image
- **Documented:** No

---

### LoadImageDataSetFromFolder

- **Category:** image
- **Documented:** No

---

### LoadImageFromFolder

- **Category:** 🤖QWEN3VL_API
- **Documented:** Yes

**Purpose:** Загрузка изображений из папки

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| folder_path | STRING |  | Путь к папке |
| image_limit | INT | 0 |  |
| start_index | INT | 0 |  |
| sort_method | ['None', 'Alphabetical (ASC)', 'Alphabetical (DESC)', 'Numerical (ASC)', 'Numerical (DESC)', 'Datetime (ASC)', 'Datetime (DESC)'] |  |  |

**Outputs:**
- `images` (IMAGE): 
- `file_paths` (STRING): 

---

### LoadImageMask

- **Category:** image
- **Documented:** No

---

### LoadImageOutput

- **Category:** image
- **Documented:** No

---

### LoadImageTextDataSetFromFolder

- **Category:** image
- **Documented:** No

---

### LoadLatent

- **Category:** model/latent
- **Documented:** No

---

### LoadMediaPipeFaceLandmarker

- **Category:** model/loaders
- **Documented:** No

---

### LoadMoGeModel

- **Category:** model/loaders
- **Documented:** No

---

### LoadTrainingDataset

- **Category:** model/training
- **Documented:** No

---

### LoadVideo

- **Category:** video
- **Documented:** No

---

### LoadVideoDataSetFromFolder

- **Category:** video
- **Documented:** No

---

### LoadVideoFromFolder

- **Category:** 🤖QWEN3VL_API
- **Documented:** Yes

**Purpose:** Загрузка видео из папки

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| folder_path | STRING |  | Путь к папке |
| video_limit | INT | 0 |  |
| start_index | INT | 0 |  |
| sort_method | ['None', 'Alphabetical (ASC)', 'Alphabetical (DESC)', 'Numerical (ASC)', 'Numerical (DESC)', 'Datetime (ASC)', 'Datetime (DESC)'] |  |  |

**Outputs:**
- `videos` (VIDEO): 
- `file_paths` (STRING): 

---

### LoadVideoTextDataSetFromFolder

- **Category:** video
- **Documented:** No

---

### LoraLoader

- **Category:** model/loaders
- **Documented:** No

---

### LoraLoaderBypass

- **Category:** model/loaders
- **Documented:** No

---

### LoraLoaderBypassModelOnly

- **Category:** model/loaders
- **Documented:** No

---

### LoraLoaderModelOnly

- **Category:** model/loaders
- **Documented:** No

---

### LoraModelLoader

- **Category:** model/loaders
- **Documented:** No

---

### LoraSave

- **Category:** experimental
- **Documented:** No

---

### LossGraphNode

- **Category:** model/training
- **Documented:** No

---

### LotusConditioning

- **Category:** model/conditioning/lotus
- **Documented:** No

---

### LtxApi25AudioToVideo

- **Category:** partner/video/LTXV
- **Documented:** No

---

### LtxApi25ImageToVideo

- **Category:** partner/video/LTXV
- **Documented:** No

---

### LtxApi25TextToVideo

- **Category:** partner/video/LTXV
- **Documented:** No

---

### LtxvApiImageToVideo

- **Category:** partner/video/LTXV
- **Documented:** No

---

### LtxvApiTextToVideo

- **Category:** partner/video/LTXV
- **Documented:** No

---

### LumaConceptsNode

- **Category:** partner/video/Luma
- **Documented:** No

---

### LumaImageEditNode2

- **Category:** partner/image/Luma
- **Documented:** No

---

### LumaImageModifyNode

- **Category:** partner/image/Luma
- **Documented:** No

---

### LumaImageNode

- **Category:** partner/image/Luma
- **Documented:** No

---

### LumaImageNode2

- **Category:** partner/image/Luma
- **Documented:** No

---

### LumaImageToVideoNode

- **Category:** partner/video/Luma
- **Documented:** No

---

### LumaRay32ExtendVideoNode

- **Category:** partner/video/Luma
- **Documented:** No

---

### LumaRay32ImageToVideoNode

- **Category:** partner/video/Luma
- **Documented:** No

---

### LumaRay32KeyframeNode

- **Category:** partner/video/Luma
- **Documented:** No

---

### LumaRay32KeyframesToVideoNode

- **Category:** partner/video/Luma
- **Documented:** No

---

### LumaRay32TextToVideoNode

- **Category:** partner/video/Luma
- **Documented:** No

---

### LumaRay32VideoEditNode

- **Category:** partner/video/Luma
- **Documented:** No

---

### LumaRay32VideoReframeNode

- **Category:** partner/video/Luma
- **Documented:** No

---

### LumaReferenceNode

- **Category:** partner/image/Luma
- **Documented:** No

---

### LumaVideoNode

- **Category:** partner/video/Luma
- **Documented:** No

---

### MagnificImageRelightNode

- **Category:** partner/image/Magnific
- **Documented:** No

---

### MagnificImageSkinEnhancerNode

- **Category:** partner/image/Magnific
- **Documented:** No

---

### MagnificImageStyleTransferNode

- **Category:** partner/image/Magnific
- **Documented:** No

---

### MagnificImageUpscalerCreativeNode

- **Category:** partner/image/Magnific
- **Documented:** No

---

### MagnificImageUpscalerPreciseV2Node

- **Category:** partner/image/Magnific
- **Documented:** No

---

### Mahiro

- **Category:** experimental
- **Documented:** No

---

### MakeTrainingDataset

- **Category:** model/training
- **Documented:** No

---

### ManualSigmas

- **Category:** model/sampling/sigmas
- **Documented:** No

---

### MaskComposite

- **Category:** image/mask
- **Documented:** No

---

### MaskPreview

- **Category:** image/mask
- **Documented:** No

---

### MaskToImage

- **Category:** image/mask
- **Documented:** No

---

### Media Form Post Node

- **Category:** RequestNode/Post Request
- **Documented:** Yes

**Purpose:** Отправка мультимедиа (IMAGE/AUDIO/VIDEO) через multipart/form-data

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| target_url | STRING | http://127.0.0.1:8000/api/upload | URL для запроса |

**Outputs:**
- `text` (STRING): Ответ как текст
- `response_bytes` (BYTES): Ответ как байты
- `json` (JSON): Ответ как JSON
- `status_code` (INT): HTTP статус код
- `response_headers` (DICT): Заголовки ответа

**Related:** Form Post Request Node, Binary Post Request Node

---

### MediaPipeFaceLandmarker

- **Category:** image/detection
- **Documented:** No

---

### MediaPipeFaceMask

- **Category:** image/detection
- **Documented:** No

---

### MediaPipeFaceMeshVisualize

- **Category:** image/detection
- **Documented:** No

---

### MergeImageLists

- **Category:** image/batch
- **Documented:** No

---

### MergeMeshes

- **Category:** 3d/mesh
- **Documented:** No

---

### MergeSplat

- **Category:** 3d/splat
- **Documented:** No

---

### MergeTextLists

- **Category:** text
- **Documented:** No

---

### MeshSmoothNormals

- **Category:** 3d/mesh
- **Documented:** No

---

### MeshTextureToImage

- **Category:** 3d/texturing
- **Documented:** No

---

### MeshToFile3D

- **Category:** 3d
- **Documented:** No

---

### MeshyAnimateModelNode

- **Category:** partner/3d/Meshy
- **Documented:** No

---

### MeshyImageToModelNode

- **Category:** partner/3d/Meshy
- **Documented:** No

---

### MeshyMultiImageToModelNode

- **Category:** partner/3d/Meshy
- **Documented:** No

---

### MeshyRefineNode

- **Category:** partner/3d/Meshy
- **Documented:** No

---

### MeshyRigModelNode

- **Category:** partner/3d/Meshy
- **Documented:** No

---

### MeshyTextToModelNode

- **Category:** partner/3d/Meshy
- **Documented:** No

---

### MeshyTextureMultiViewNode

- **Category:** partner/3d/Meshy
- **Documented:** No

---

### MeshyTextureNode

- **Category:** partner/3d/Meshy
- **Documented:** No

---

### MetaMuseImageEditApi

- **Category:** partner/image/Meta
- **Documented:** No

---

### MetaMuseImageTextToImageApi

- **Category:** partner/image/Meta
- **Documented:** No

---

### MiniMaxH3AddGuide

- **Category:** model/conditioning/minimax
- **Documented:** No

---

### MiniMaxH3ImageToVideo

- **Category:** model/conditioning/minimax
- **Documented:** No

---

### MiniMaxH3ReferenceToVideo

- **Category:** model/conditioning/minimax
- **Documented:** No

---

### MiniMaxH3SigmaShift

- **Category:** model/patch/minimax
- **Documented:** No

---

### MiniMaxMusic3TextEncode

- **Category:** model/conditioning/minimax music
- **Documented:** No

---

### MinimaxHailuo03ContextIRNode

- **Category:** partner/video/MiniMax
- **Documented:** No

---

### MinimaxHailuo03FirstLastFrameNode

- **Category:** partner/video/MiniMax
- **Documented:** No

---

### MinimaxHailuo03ReferenceNode

- **Category:** partner/video/MiniMax
- **Documented:** No

---

### MinimaxHailuo03RegenerateNode

- **Category:** partner/video/MiniMax
- **Documented:** No

---

### MinimaxHailuo03TextToVideoNode

- **Category:** partner/video/MiniMax
- **Documented:** No

---

### MinimaxHailuoVideoNode

- **Category:** partner/video/MiniMax
- **Documented:** No

---

### MinimaxImageToVideoNode

- **Category:** partner/video/MiniMax
- **Documented:** No

---

### MinimaxTextToVideoNode

- **Category:** partner/video/MiniMax
- **Documented:** No

---

### MoGeGeometryToFOV

- **Category:** image/geometry estimation
- **Documented:** No

---

### MoGeInference

- **Category:** image/geometry estimation
- **Documented:** No

---

### MoGePanoramaInference

- **Category:** image/geometry estimation
- **Documented:** No

---

### MoGePointMapToMesh

- **Category:** image/geometry estimation
- **Documented:** No

---

### MoGeRender

- **Category:** image/geometry estimation
- **Documented:** No

---

### ModelAttentionBackend

- **Category:** model/patch
- **Documented:** No

---

### ModelComputeDtype

- **Category:** advanced/debug
- **Documented:** No

---

### ModelMergeAdd

- **Category:** model/merging
- **Documented:** No

---

### ModelMergeAuraflow

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeBlocks

- **Category:** model/merging
- **Documented:** No

---

### ModelMergeCosmos14B

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeCosmos7B

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeCosmosPredict2_14B

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeCosmosPredict2_2B

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeFlux1

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeKrea2

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeLTXV

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeMochiPreview

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeQwenImage

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeSD1

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeSD2

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeSD35_Large

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeSD3_2B

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeSDXL

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelMergeSimple

- **Category:** model/merging
- **Documented:** No

---

### ModelMergeSubtract

- **Category:** model/merging
- **Documented:** No

---

### ModelMergeWAN2_1

- **Category:** model/merging/model specific
- **Documented:** No

---

### ModelNoiseScale

- **Category:** model/patch
- **Documented:** No

---

### ModelPatchLoader

- **Category:** model/loaders
- **Documented:** No

---

### ModelSamplingAuraFlow

- **Category:** model/patch
- **Documented:** No

---

### ModelSamplingContinuousEDM

- **Category:** model/patch
- **Documented:** No

---

### ModelSamplingContinuousV

- **Category:** model/patch
- **Documented:** No

---

### ModelSamplingDiscrete

- **Category:** model/patch
- **Documented:** No

---

### ModelSamplingFlux

- **Category:** model/patch/flux
- **Documented:** No

---

### ModelSamplingLTXV

- **Category:** model/patch/ltxv
- **Documented:** No

---

### ModelSamplingSD3

- **Category:** model/patch/stable diffusion
- **Documented:** No

---

### ModelSamplingStableCascade

- **Category:** model/patch/stable cascade
- **Documented:** No

---

### ModelSave

- **Category:** model/merging
- **Documented:** No

---

### Morphology

- **Category:** image/filters
- **Documented:** No

---

### MultiGPU_WorkUnits

- **Category:** advanced/multigpu
- **Documented:** No

---

### NAGuidance

- **Category:** advanced/guidance
- **Documented:** No

---

### NormalizeImages

- **Category:** image/color
- **Documented:** No

---

### NormalizeVideoLatentStart

- **Category:** model/conditioning
- **Documented:** No

---

### OpenAIChatConfig

- **Category:** partner/text/OpenAI
- **Documented:** No

---

### OpenAIChatNode

- **Category:** partner/text/OpenAI
- **Documented:** No

---

### OpenAICompatibleChat

- **Category:** api/text
- **Documented:** Yes

**Purpose:** Чат с LLM через OpenAI-compatible API

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| base_url | STRING | https://api.openai.com/v1 | URL endpoint |
| api_key | STRING |  | API ключ (или env OPENAI_COMPATIBLE_API_KEY) |
| model | COMBO | (press Refresh models) | Модель для использования |
| prompts | COMFY_AUTOGROW_V3 |  |  |

**Outputs:**
- `text` (STRING): Ответ модели

**Configuration:**
- API key: можно задать через env переменные
- Models: автозагрузка через /models endpoint
- Max inputs: 16 текстовых входов

**Related:** OpenAI API, OpenRouter, Groq, LM Studio, Ollama

---

### OpenAIDalle2

- **Category:** partner/image/OpenAI
- **Documented:** No

---

### OpenAIDalle3

- **Category:** partner/image/OpenAI
- **Documented:** No

---

### OpenAIGPTImage1

- **Category:** partner/image/OpenAI
- **Documented:** No

---

### OpenAIGPTImageNodeV2

- **Category:** partner/image/OpenAI
- **Documented:** No

---

### OpenAIInputFiles

- **Category:** partner/text/OpenAI
- **Documented:** No

---

### OpenAIVideoSora2

- **Category:** partner/video/Sora
- **Documented:** No

---

### OpenRouterLLMNode

- **Category:** partner/text/OpenRouter
- **Documented:** No

---

### OpenRouterNode

- **Category:** LLM
- **Documented:** Yes

**Purpose:** Логирование/отладка workflow (placeholder node)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| api_key | STRING |  |  |
| system_prompt | STRING | You are a helpful assistant. |  |
| user_message_box | STRING | Hello, how are you? |  |
| model | ['error_fetching_models', 'google/gemma-3-27b-it', 'openai/gpt-4o'] |  |  |
| web_search | BOOLEAN | False |  |
| cheapest | BOOLEAN | True |  |
| fastest | BOOLEAN | False |  |
| image_generation | BOOLEAN | False |  |
| temperature | FLOAT | 1.0 |  |
| pdf_engine | ['auto', 'mistral-ocr', 'pdf-text'] | auto |  |
| chat_mode | BOOLEAN | False |  |

**Outputs:**
- `Output` (STRING): 
- `image` (IMAGE): 
- `Stats` (STRING): 
- `Credits` (STRING): 

**Related:** OpenRouter LLM nodes

---

### OpticalFlowLoader

- **Category:** model/loaders
- **Documented:** No

---

### OptimalStepsScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### PaintMesh

- **Category:** 3d/mesh
- **Documented:** No

---

### Painter

- **Category:** image
- **Documented:** No

---

### PairConditioningCombine

- **Category:** advanced/hooks/cond pair
- **Documented:** No

---

### PairConditioningSetDefaultCombine

- **Category:** advanced/hooks/cond pair
- **Documented:** No

---

### PairConditioningSetProperties

- **Category:** advanced/hooks/cond pair
- **Documented:** No

---

### PairConditioningSetPropertiesAndCombine

- **Category:** advanced/hooks/cond pair
- **Documented:** No

---

### PatchModelAddDownscale

- **Category:** model/patch/unet
- **Documented:** No

---

### PerpNeg

- **Category:** experimental
- **Documented:** No

---

### PerpNegGuider

- **Category:** experimental
- **Documented:** No

---

### PerturbedAttentionGuidance

- **Category:** model/patch/unet
- **Documented:** No

---

### PhotoMakerEncode

- **Category:** model/conditioning/photomaker
- **Documented:** No

---

### PhotoMakerLoader

- **Category:** model/loaders
- **Documented:** No

---

### PiDConditioning

- **Category:** model/conditioning
- **Documented:** No

---

### Pixal3DConditioning

- **Category:** model/conditioning/trellis2
- **Documented:** No

---

### PixverseImageToVideoNode

- **Category:** partner/video/PixVerse
- **Documented:** No

---

### PixverseTemplateNode

- **Category:** partner/video/PixVerse
- **Documented:** No

---

### PixverseTextToVideoNode

- **Category:** partner/video/PixVerse
- **Documented:** No

---

### PixverseTransitionVideoNode

- **Category:** partner/video/PixVerse
- **Documented:** No

---

### PixverseV6ExtendVideoNode

- **Category:** partner/video/PixVerse
- **Documented:** No

---

### PixverseV6FirstLastFrameNode

- **Category:** partner/video/PixVerse
- **Documented:** No

---

### PixverseV6FusionVideoNode

- **Category:** partner/video/PixVerse
- **Documented:** No

---

### PixverseV6ImageToVideoNode

- **Category:** partner/video/PixVerse
- **Documented:** No

---

### PixverseV6TextToVideoNode

- **Category:** partner/video/PixVerse
- **Documented:** No

---

### PollinationsAudioGen

- **Category:** Pollinations/Audio
- **Documented:** Yes

**Purpose:** Генерация аудио через Pollinations AI

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| text | STRING | Hello world |  |
| model | ['elevenlabs', 'elevenmusic', 'scribe', 'suno', 'whisper'] | elevenlabs | Модель |
| voice | ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer', 'sarah', 'rachel', 'charlie'] | sarah |  |

**Outputs:**
- `audio_url` (STRING): 

---

### PollinationsBYOPLogin

- **Category:** Pollinations/BYOP
- **Documented:** Yes

**Purpose:** Аутентификация для BYOP (Bring Your Own Provider)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| login_trigger | BOOLEAN | False |  |

**Outputs:**
- `api_key` (STRING): 
- `username` (STRING): 
- `email` (STRING): 
- `balance` (INT): 

---

### PollinationsImageGen

- **Category:** Pollinations/Image
- **Documented:** Yes

**Purpose:** Генерация изображений через Pollinations AI

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| prompt | STRING | a cat in space | Текст-промпт для генерации |
| model | ['flux', 'flux-2-dev', 'gptimage', 'gptimage-large 💎', 'grok-imagine', 'imagen-4', 'klein', 'klein-large', 'kontext 💎', 'nanobanana 💎', 'nanobanana-2 💎', 'nanobanana-pro 💎', 'seedream5 💎', 'zimage'] | flux | Модель |
| width | INT | 1024 | Ширина |
| height | INT | 1024 | Высота |
| seed | INT | 42 | Сид |

**Outputs:**
- `image` (IMAGE): 
- `url` (STRING): 

**Configuration:**
- API key: Не требуется (бесплатный API)
- Rate limit: ~10 requests/min

**Related:** PollinationsTextGen, PollinationsAudioGen

---

### PollinationsTextGen

- **Category:** Pollinations/Text
- **Documented:** Yes

**Purpose:** Генерация текста через Pollinations AI

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| prompt | STRING | Hi! | Текст-промпт |
| model | ['claude 💎', 'claude-fast', 'claude-large 💎', 'deepseek', 'gemini 💎', 'gemini-fast', 'gemini-large 💎', 'gemini-search', 'glm', 'grok 💎', 'kimi', 'midijourney', 'minimax', 'mistral', 'nomnom', 'nova-fast', 'openai', 'openai-audio', 'openai-fast', 'openai-large 💎', 'perplexity-fast', 'perplexity-reasoning', 'polly', 'qwen-character', 'qwen-coder', 'qwen-safety', 'step-3.5-flash'] | openai | Модель |
| system_instruction | STRING | You are a helpful assistant. |  |

**Outputs:**
- `STRING` (STRING): Сгенерированный текст

---

### PollinationsVideoGen

- **Category:** Pollinations/Video
- **Documented:** Yes

**Purpose:** Генерация видео через Pollinations AI

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| prompt | STRING | cinematic sunset | Текст-промпт |
| model | ['grok-video', 'ltx-2 💎', 'seedance 💎', 'seedance-pro 💎', 'veo 💎', 'wan 💎'] | wan |  |

**Outputs:**
- `video_url` (STRING): 

---

### PolyexponentialScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### PorterDuffImageComposite

- **Category:** image/compositing
- **Documented:** No

---

### Post Request Node

- **Category:** RequestNode/Post Request
- **Documented:** Yes

**Purpose:** HTTP POST запрос с JSON body

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| target_url | STRING | https://example.com/api | URL для запроса |
| request_body | STRING | {} |  |

**Outputs:**
- `text` (STRING): Ответ как текст
- `file` (BYTES): Ответ как байты
- `json` (JSON): Ответ как JSON
- `any` (ANY): Ответ как байты

**Configuration:**
- proxy: Не используется
- content-type: application/json

**Related:** Get Request Node, Rest Api Node, Form Post Request Node

---

### Preview3D

- **Category:** 3d
- **Documented:** No

---

### Preview3DAdvanced

- **Category:** 3d
- **Documented:** No

---

### PreviewAny

- **Category:** utilities
- **Documented:** No

---

### PreviewAudio

- **Category:** audio
- **Documented:** No

---

### PreviewGaussianSplat

- **Category:** 3d
- **Documented:** No

---

### PreviewImage

- **Category:** image
- **Documented:** No

---

### PreviewPointCloud

- **Category:** 3d
- **Documented:** No

---

### PrimitiveBoolean

- **Category:** utilities/primitive
- **Documented:** No

---

### PrimitiveBoundingBox

- **Category:** utilities/primitive
- **Documented:** No

---

### PrimitiveFloat

- **Category:** utilities/primitive
- **Documented:** No

---

### PrimitiveInt

- **Category:** utilities/primitive
- **Documented:** No

---

### PrimitiveString

- **Category:** utilities/primitive
- **Documented:** No

---

### PrimitiveStringMultiline

- **Category:** utilities/primitive
- **Documented:** No

---

### QWEN3VL_Image

- **Category:** 🤖QWEN3VL_API
- **Documented:** Yes

**Purpose:** Анализ изображения через Qwen3-VL

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| image | IMAGE |  | Входное изображение |
| model | ['qwen3-vl-flash', 'qwen3-vl-flash-2025-10-15', 'qwen3-vl-plus', 'qwen3-vl-plus-2025-09-23', 'qwen-vl-max'] |  |  |
| user_prompt | STRING | 请描述这张图片 |  |
| seed | INT | 0 |  |

**Outputs:**
- `text` (STRING): 

---

### QWEN3VL_Video

- **Category:** 🤖QWEN3VL_API
- **Documented:** Yes

**Purpose:** Анализ видео через Qwen3-VL

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| video_path | STRING |  |  |
| model | ['qwen3-vl-flash', 'qwen3-vl-flash-2025-10-15', 'qwen3-vl-plus', 'qwen3-vl-plus-2025-09-23', 'qwen-vl-max'] |  |  |
| user_prompt | STRING | 请描述这个视频的内容 |  |
| seed | INT | 0 |  |

**Outputs:**
- `text` (STRING): 

---

### QWEN3_Text

- **Category:** 🤖QWEN3VL_API
- **Documented:** Yes

**Purpose:** Генерация текста через Qwen3

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| model | ['qwen3-max', 'qwen-plus', 'qwen-flash'] |  |  |
| user_prompt | STRING | 你好,请介绍一下你自己 |  |
| system_prompt | STRING | You are a helpful assistant. |  |
| temperature | FLOAT | 0.7 |  |
| top_p | FLOAT | 0.8 |  |
| seed | INT | 0 |  |

**Outputs:**
- `response` (STRING): 
- `conversation_history` (STRING): 

---

### QWEN_APIKey

- **Category:** 🤖QWEN3VL_API
- **Documented:** Yes

**Purpose:** Установка API ключа для Qwen

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| api_key | STRING |  | API ключ |

**Outputs:**
- `api_key` (STRING): 

---

### QWEN_TextDisplay

- **Category:** 🤖QWEN3VL_API
- **Documented:** No

---

### QWEN_TextOperation

- **Category:** 🤖QWEN3VL_API
- **Documented:** Yes

**Purpose:** Операции с текстом (конкатенация, замена)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| text | STRING |  |  |

**Outputs:**
- `text` (STRING): 

---

### QWEN_TextProcess

- **Category:** 🤖QWEN3VL_API
- **Documented:** Yes

**Purpose:** Обработка текста (подсчет токенов и т.д.)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| text | STRING |  | Входной текст |
| main_operation_1 | ['不改变', '去换行', '去空行', '去空格', '添加编号', '统计字数'] |  |  |
| main_operation_2 | ['不改变', '去换行', '去空行', '去空格', '添加编号', '统计字数'] |  |  |

**Outputs:**
- `text` (STRING): 
- `count` (INT): 

---

### QWenVL_API_S_Multi_Zho

- **Category:** Zho模块组/💫QWenVL
- **Documented:** Yes

**Purpose:** Многоязычное распознавание текста на изображении

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| image | IMAGE |  | Входное изображение |
| prompt | STRING | Describe this image | Дополнительный запрос |
| model_name | ['qwen-vl-plus', 'qwen-vl-max'] |  |  |
| seed | INT | 0 |  |

**Outputs:**
- `text` (STRING): Распознанный текст

---

### QWenVL_API_S_Zho

- **Category:** Zho模块组/💫QWenVL
- **Documented:** Yes

**Purpose:** Распознавание текста на изображении (Chinese OCR)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| image | IMAGE |  | Входное изображение |
| prompt | STRING | Describe this image | Дополнительный запрос |
| model_name | ['qwen-vl-plus', 'qwen-vl-max'] |  |  |
| seed | INT | 0 |  |

**Outputs:**
- `text` (STRING): Распознанный текст

**Configuration:**
- API key: через `config.json` (QWENVL_API_KEY)

---

### QuadrupleCLIPLoader

- **Category:** model/loaders
- **Documented:** No

---

### QuiverImageToSVGNode

- **Category:** partner/image/Quiver
- **Documented:** No

---

### QuiverTextToSVGNode

- **Category:** partner/image/Quiver
- **Documented:** No

---

### QwenImageDiffsynthControlnet

- **Category:** model/patch/qwen
- **Documented:** No

---

### QwenImageEditApi

- **Category:** partner/image/Qwen
- **Documented:** No

---

### QwenImageTextToImageApi

- **Category:** partner/image/Qwen
- **Documented:** No

---

### QwenVL-F

- **Category:** QwenVL-F
- **Documented:** No

---

### QwenVL-F_Advanced

- **Category:** QwenVL-F
- **Documented:** No

---

### QwenVL-F_GGUF

- **Category:** QwenVL-F
- **Documented:** No

---

### QwenVL-F_GGUF_Advanced

- **Category:** QwenVL-F
- **Documented:** No

---

### QwenVL-F_PromptEnhancer

- **Category:** QwenVL-F
- **Documented:** No

---

### RTDETR_detect

- **Category:** image/detection
- **Documented:** No

---

### RandomCropImages

- **Category:** image/transform
- **Documented:** No

---

### RandomNoise

- **Category:** model/sampling/noise
- **Documented:** No

---

### ReActorBuildFaceModel

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorFaceBoost

- **Category:** 🌌 ReActor
- **Documented:** Yes

**Purpose:** Улучшение качества лиц (boost)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| enabled | BOOLEAN | True | Включить |
| boost_model | ['none', 'codeformer-v0.1.0.pth', 'GFPGANv1.3.pth', 'GFPGANv1.4.pth', 'GPEN-BFR-512.onnx'] |  | Модель улучшения |
| interpolation | ['Nearest', 'Bilinear', 'Bicubic', 'Lanczos'] | Bicubic | Интерполяция |
| visibility | FLOAT | 1 | Видимость |
| codeformer_weight | FLOAT | 0.5 | Вес CodeFormer |
| restore_with_main_after | BOOLEAN | False | Восстановление после main |

**Outputs:**
- `FACE_BOOST` (FACE_BOOST): Boost модель

---

### ReActorFaceSimilarity

- **Category:** 🌌 ReActor
- **Documented:** Yes

**Purpose:** Сравнение схожести лиц

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| image1 | IMAGE |  | Первое изображение |
| image2 | IMAGE |  | Второе изображение |

**Outputs:**
- `similarity_float` (FLOAT): 
- `similarity_text` (STRING): 

---

### ReActorFaceSwap

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorFaceSwapOpt

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorImageDublicator

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorLoadFaceModel

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorMakeFaceModelBatch

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorMaskHelper

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorOptions

- **Category:** 🌌 ReActor
- **Documented:** Yes

**Purpose:** Настройки порядка лиц

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| input_faces_order | ['left-right', 'right-left', 'top-bottom', 'bottom-top', 'small-large', 'large-small'] | large-small | Порядок входных лиц |
| input_faces_index | STRING | 0 | Индексы |
| detect_gender_input | ['no', 'female', 'male'] | no | Пол |
| source_faces_order | ['left-right', 'right-left', 'top-bottom', 'bottom-top', 'small-large', 'large-small'] | large-small | Порядок исходных лиц |
| source_faces_index | STRING | 0 | Индексы |
| detect_gender_source | ['no', 'female', 'male'] | no | Пол |
| console_log_level | [0, 1, 2] | 1 | Уровень логов |
| restore_swapped_only | BOOLEAN | True |  |

**Outputs:**
- `OPTIONS` (OPTIONS): Настройки

---

### ReActorRestoreFace

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorRestoreFaceAdvanced

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorSaveFaceModel

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorSetWeight

- **Category:** 🌌 ReActor
- **Documented:** No

---

### ReActorUnload

- **Category:** 🌌 ReActor
- **Documented:** Yes

**Purpose:** Выгрузка моделей из памяти

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| trigger | IMAGE |  | Триггер (любое изображение) |

**Outputs:**
- `IMAGE` (IMAGE): То же изображение (для continuation)

---

### RebatchImages

- **Category:** image/batch
- **Documented:** No

---

### RebatchLatents

- **Category:** model/latent/batch
- **Documented:** No

---

### RecordAudio

- **Category:** audio
- **Documented:** No

---

### RecraftColorRGB

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftControls

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftCreateStyleNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftCreativeUpscaleNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftCrispUpscaleNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftImageInpaintingNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftImageToImageNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftRemoveBackgroundNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftReplaceBackgroundNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftStyleV3DigitalIllustration

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftStyleV3InfiniteStyleLibrary

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftStyleV3LogoRaster

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftStyleV3RealisticImage

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftTextToImageNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftTextToVectorNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftV4CreateStyleNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftV4TextToImageNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftV4TextToVectorNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### RecraftVectorizeImageNode

- **Category:** partner/image/Recraft
- **Documented:** No

---

### ReferenceLatent

- **Category:** model/conditioning
- **Documented:** No

---

### ReferenceTimbreAudio

- **Category:** model/conditioning
- **Documented:** No

---

### RegexExtract

- **Category:** text
- **Documented:** No

---

### RegexMatch

- **Category:** text
- **Documented:** No

---

### RegexReplace

- **Category:** text
- **Documented:** No

---

### RemeshMesh

- **Category:** 3d/mesh
- **Documented:** No

---

### RemoveBackground

- **Category:** image/background removal
- **Documented:** No

---

### RenderMesh

- **Category:** 3d/mesh
- **Documented:** No

---

### RenderSplat

- **Category:** 3d/splat
- **Documented:** No

---

### RenderUVAtlas

- **Category:** 3d/texturing
- **Documented:** No

---

### RenormCFG

- **Category:** model/patch
- **Documented:** No

---

### RepeatImageBatch

- **Category:** image/batch
- **Documented:** No

---

### RepeatLatentBatch

- **Category:** model/latent/batch
- **Documented:** No

---

### ReplaceText

- **Category:** text
- **Documented:** No

---

### ReplaceVideoLatentFrames

- **Category:** model/latent/batch
- **Documented:** No

---

### RescaleCFG

- **Category:** model/patch
- **Documented:** No

---

### ResizeAndPadImage

- **Category:** image/transform
- **Documented:** No

---

### ResizeImageMaskNode

- **Category:** image/transform
- **Documented:** No

---

### ResizeImagesByLongerEdge

- **Category:** image/transform
- **Documented:** No

---

### ResizeImagesByShorterEdge

- **Category:** image/transform
- **Documented:** No

---

### ResolutionBucket

- **Category:** model/training
- **Documented:** No

---

### ResolutionSelector

- **Category:** utilities
- **Documented:** No

---

### Rest Api Node

- **Category:** RequestNode/REST API
- **Documented:** Yes

**Purpose:** Универсальный HTTP запрос (GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| target_url | STRING | https://example.com/api | URL для запроса |
| request_body | STRING | {} |  |
| method | ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'] | GET | HTTP метод |

**Outputs:**
- `text` (STRING): Ответ как текст
- `file` (BYTES): Ответ как байты
- `json` (JSON): Ответ как JSON
- `headers` (DICT): Заголовки ответа
- `status_code` (INT): HTTP статус код
- `any` (ANY): Ответ как байты

**Configuration:**
- supports_retry: Да (через Retry Settings Node)
- timeout: System default

**Related:** Get Request Node, Post Request Node, Retry Settings Node

---

### Retry Settings Node

- **Category:** RequestNode/KeyValue
- **Documented:** Yes

**Purpose:** Конфигурация повторных попыток для HTTP запросов

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| key | ['max_retry', 'retry_interval', 'retry_until_status_code', 'retry_until_not_status_code'] |  |  |
| value | INT | 3 |  |

**Outputs:**
- `RETRY_SETTING` (RETRY_SETTING): Конфигурация retry

**Related:** Rest Api Node

---

### ReveImageCreateNode

- **Category:** partner/image/Reve
- **Documented:** No

---

### ReveImageEditNode

- **Category:** partner/image/Reve
- **Documented:** No

---

### ReveImageRemixNode

- **Category:** partner/image/Reve
- **Documented:** No

---

### Rodin3D_Detail

- **Category:** partner/3d/Rodin
- **Documented:** No

---

### Rodin3D_Gen2

- **Category:** partner/3d/Rodin
- **Documented:** No

---

### Rodin3D_Gen25_Image

- **Category:** partner/3d/Rodin
- **Documented:** No

---

### Rodin3D_Gen25_Text

- **Category:** partner/3d/Rodin
- **Documented:** No

---

### Rodin3D_Regular

- **Category:** partner/3d/Rodin
- **Documented:** No

---

### Rodin3D_Sketch

- **Category:** partner/3d/Rodin
- **Documented:** No

---

### Rodin3D_Smooth

- **Category:** partner/3d/Rodin
- **Documented:** No

---

### RotateMesh

- **Category:** 3d/mesh
- **Documented:** No

---

### RunwayAleph2KeyframeNode

- **Category:** partner/video/Runway
- **Documented:** No

---

### RunwayAleph2PromptImageNode

- **Category:** partner/video/Runway
- **Documented:** No

---

### RunwayAleph2VideoToVideoNode

- **Category:** partner/video/Runway
- **Documented:** No

---

### RunwayFirstLastFrameNode

- **Category:** partner/video/Runway
- **Documented:** No

---

### RunwayImageToVideoNodeGen3a

- **Category:** partner/video/Runway
- **Documented:** No

---

### RunwayImageToVideoNodeGen4

- **Category:** partner/video/Runway
- **Documented:** No

---

### RunwayTextToImageNode

- **Category:** partner/image/Runway
- **Documented:** No

---

### SAM3DBody_FaceExpression

- **Category:** image/detection
- **Documented:** No

---

### SAM3DBody_Loader

- **Category:** image/detection
- **Documented:** No

---

### SAM3DBody_Predict

- **Category:** image/detection
- **Documented:** No

---

### SAM3DBody_Render

- **Category:** image/detection
- **Documented:** No

---

### SAM3DBody_Smooth

- **Category:** image/detection
- **Documented:** No

---

### SAM3_Detect

- **Category:** image/detection
- **Documented:** No

---

### SAM3_TrackPreview

- **Category:** image/detection
- **Documented:** No

---

### SAM3_TrackToMask

- **Category:** image/detection
- **Documented:** No

---

### SAM3_VideoTrack

- **Category:** image/detection
- **Documented:** No

---

### SCAIL2ColoredMask

- **Category:** model/conditioning/wan/scail
- **Documented:** No

---

### SDPoseDrawKeypoints

- **Category:** image/detection
- **Documented:** No

---

### SDPoseFaceBBoxes

- **Category:** image/detection
- **Documented:** No

---

### SDPoseKeypointExtractor

- **Category:** image/detection
- **Documented:** No

---

### SDTurboScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### SD_4XUpscale_Conditioning

- **Category:** model/conditioning/stable diffusion upscaler
- **Documented:** No

---

### SUPIRApply

- **Category:** model/patch/supir
- **Documented:** No

---

### SV3D_Conditioning

- **Category:** model/conditioning/stable video 3d
- **Documented:** No

---

### SVD_img2vid_Conditioning

- **Category:** model/conditioning/stable video
- **Documented:** No

---

### SamplerARVideo

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerCustom

- **Category:** model/sampling/custom
- **Documented:** No

---

### SamplerCustomAdvanced

- **Category:** model/sampling/custom
- **Documented:** No

---

### SamplerDPMAdaptative

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerDPMPP_2M_SDE

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerDPMPP_2S_Ancestral

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerDPMPP_3M_SDE

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerDPMPP_SDE

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerER_SDE

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerEulerAncestral

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerEulerAncestralCFGPP

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerEulerCFGpp

- **Category:** experimental
- **Documented:** No

---

### SamplerLCM

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerLCMUpscale

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerLMS

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerSASolver

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplerSEEDS2

- **Category:** model/sampling/samplers
- **Documented:** No

---

### SamplingPercentToSigma

- **Category:** model/sampling/sigmas
- **Documented:** No

---

### Save3DAdvanced

- **Category:** 3d
- **Documented:** No

---

### SaveAnimatedPNG

- **Category:** image
- **Documented:** No

---

### SaveAnimatedWEBP

- **Category:** image
- **Documented:** No

---

### SaveAudio

- **Category:** audio
- **Documented:** No

---

### SaveAudioAdvanced

- **Category:** audio
- **Documented:** No

---

### SaveAudioMP3

- **Category:** audio
- **Documented:** No

---

### SaveAudioOpus

- **Category:** audio
- **Documented:** No

---

### SaveGLB

- **Category:** 3d
- **Documented:** No

---

### SaveGaussianSplat

- **Category:** 3d
- **Documented:** No

---

### SaveImage

- **Category:** image
- **Documented:** No

---

### SaveImageAdvanced

- **Category:** image
- **Documented:** No

---

### SaveImageDataSetToFolder

- **Category:** image
- **Documented:** No

---

### SaveImageTextDataSetToFolder

- **Category:** image
- **Documented:** No

---

### SaveImageWebsocket

- **Category:** image
- **Documented:** Yes

**Purpose:** Сохранение изображений через WebSocket (без метаданных)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| images | IMAGE |  | Изображения для сохранения |

**Configuration:**
- Формат: PNG
- Метод: WebSocket binary transfer
- Metadata: Не сохраняется

**Related:** SaveImage, SaveImageAdvanced

---

### SaveLatent

- **Category:** model/latent
- **Documented:** No

---

### SaveLoRA

- **Category:** model/merging
- **Documented:** No

---

### SavePointCloud

- **Category:** 3d
- **Documented:** No

---

### SaveSVGNode

- **Category:** image
- **Documented:** No

---

### SaveText

- **Category:** text
- **Documented:** No

---

### SaveTrainingDataset

- **Category:** model/training
- **Documented:** No

---

### SaveVideo

- **Category:** video
- **Documented:** No

---

### SaveWEBM

- **Category:** video
- **Documented:** No

---

### ScaleROPE

- **Category:** model/patch
- **Documented:** No

---

### SeedNode

- **Category:** utilities
- **Documented:** No

---

### SeedVR2Conditioning

- **Category:** model/conditioning
- **Documented:** No

---

### SeedVR2PostProcessing

- **Category:** image/post-processors
- **Documented:** No

---

### SeedVR2Preprocess

- **Category:** image/pre-processors
- **Documented:** No

---

### SeedVR2TemporalChunk

- **Category:** model/latent/batch
- **Documented:** No

---

### SeedVR2TemporalMerge

- **Category:** model/latent/batch
- **Documented:** No

---

### SelectCLIPDevice

- **Category:** advanced/multigpu
- **Documented:** No

---

### SelectModelDevice

- **Category:** advanced/multigpu
- **Documented:** No

---

### SelectVAEDevice

- **Category:** advanced/multigpu
- **Documented:** No

---

### SelfAttentionGuidance

- **Category:** experimental
- **Documented:** No

---

### SetClipHooks

- **Category:** advanced/hooks/clip
- **Documented:** No

---

### SetFirstSigma

- **Category:** model/sampling/sigmas
- **Documented:** No

---

### SetHookKeyframes

- **Category:** advanced/hooks/scheduling
- **Documented:** No

---

### SetLatentNoiseMask

- **Category:** model/latent
- **Documented:** No

---

### SetUnionControlNetType

- **Category:** model/conditioning/controlnet
- **Documented:** No

---

### ShuffleDataset

- **Category:** image/batch
- **Documented:** No

---

### ShuffleImageTextDataset

- **Category:** image/batch
- **Documented:** No

---

### ShuffleVideoDataset

- **Category:** video/batch
- **Documented:** No

---

### ShuffleVideoTextDataset

- **Category:** dataset/video
- **Documented:** No

---

### SkipLayerGuidanceDiT

- **Category:** advanced/guidance
- **Documented:** No

---

### SkipLayerGuidanceDiTSimple

- **Category:** advanced/guidance
- **Documented:** No

---

### SkipLayerGuidanceSD3

- **Category:** advanced/guidance
- **Documented:** No

---

### SolidMask

- **Category:** image/mask
- **Documented:** No

---

### SoniloTextToMusic

- **Category:** partner/audio/Sonilo
- **Documented:** No

---

### SoniloVideoToMusic

- **Category:** partner/audio/Sonilo
- **Documented:** No

---

### SplatToFile3D

- **Category:** 3d/splat
- **Documented:** No

---

### SplatToMesh

- **Category:** 3d/splat
- **Documented:** No

---

### SplitAudioChannels

- **Category:** audio
- **Documented:** No

---

### SplitImageToTileList

- **Category:** image/batch
- **Documented:** No

---

### SplitImageWithAlpha

- **Category:** image/compositing
- **Documented:** No

---

### SplitSigmas

- **Category:** model/sampling/sigmas
- **Documented:** No

---

### SplitSigmasDenoise

- **Category:** model/sampling/sigmas
- **Documented:** No

---

### StableCascade_EmptyLatentImage

- **Category:** model/latent/stable cascade
- **Documented:** No

---

### StableCascade_StageB_Conditioning

- **Category:** model/conditioning/stable cascade
- **Documented:** No

---

### StableCascade_StageC_VAEEncode

- **Category:** model/latent/stable cascade
- **Documented:** No

---

### StableCascade_SuperResolutionControlnet

- **Category:** experimental/stable cascade
- **Documented:** No

---

### StableZero123_Conditioning

- **Category:** model/conditioning/stable zero123
- **Documented:** No

---

### StableZero123_Conditioning_Batched

- **Category:** model/conditioning/stable zero123
- **Documented:** No

---

### String Replace Node

- **Category:** RequestNode/Utils
- **Documented:** Yes

**Purpose:** Замена подстрок в строке (плейсхолдеры)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| input_string | STRING |  |  |

**Outputs:**
- `output_string` (STRING): Результат замены

**Related:** Key/Value Node

---

### StringCompare

- **Category:** text
- **Documented:** No

---

### StringConcatenate

- **Category:** text
- **Documented:** No

---

### StringContains

- **Category:** text
- **Documented:** No

---

### StringFormat

- **Category:** text
- **Documented:** No

---

### StringLength

- **Category:** text
- **Documented:** No

---

### StringReplace

- **Category:** text
- **Documented:** No

---

### StringSubstring

- **Category:** text
- **Documented:** No

---

### StringTrim

- **Category:** text
- **Documented:** No

---

### StripWhitespace

- **Category:** text
- **Documented:** No

---

### StyleModelApply

- **Category:** model/conditioning
- **Documented:** No

---

### StyleModelLoader

- **Category:** model/loaders
- **Documented:** No

---

### SyncLipSyncNode

- **Category:** partner/video/sync.so
- **Documented:** No

---

### SyncTalkingImageNode

- **Category:** partner/video/sync.so
- **Documented:** No

---

### T5TokenizerOptions

- **Category:** model/conditioning
- **Documented:** No

---

### TCFG

- **Category:** advanced/guidance
- **Documented:** No

---

### TemporalScoreRescaling

- **Category:** model/patch/unet
- **Documented:** No

---

### Tencent3DPartNode

- **Category:** partner/3d/Tencent
- **Documented:** No

---

### Tencent3DTextureEditNode

- **Category:** partner/3d/Tencent
- **Documented:** No

---

### TencentImageToModelNode

- **Category:** partner/3d/Tencent
- **Documented:** No

---

### TencentModelTo3DUVNode

- **Category:** partner/3d/Tencent
- **Documented:** No

---

### TencentSmartTopologyNode

- **Category:** partner/3d/Tencent
- **Documented:** No

---

### TencentTextToModelNode

- **Category:** partner/3d/Tencent
- **Documented:** No

---

### TextEncodeAceStepAudio

- **Category:** model/conditioning/ace
- **Documented:** No

---

### TextEncodeAceStepAudio1.5

- **Category:** model/conditioning/ace
- **Documented:** No

---

### TextEncodeBooguEdit

- **Category:** model/conditioning/boogu
- **Documented:** No

---

### TextEncodeHunyuanVideo_ImageToVideo

- **Category:** model/conditioning/hunyuan video
- **Documented:** No

---

### TextEncodeJoyImageEdit

- **Category:** model/conditioning/joyimage
- **Documented:** No

---

### TextEncodeMageFlowEdit

- **Category:** model/conditioning/mage
- **Documented:** No

---

### TextEncodeQwenImageEdit

- **Category:** model/conditioning/qwen image
- **Documented:** No

---

### TextEncodeQwenImageEditPlus

- **Category:** model/conditioning/qwen image
- **Documented:** No

---

### TextEncodeZImageOmni

- **Category:** model/conditioning/z-image
- **Documented:** No

---

### TextGenerate

- **Category:** text
- **Documented:** No

---

### TextGenerateLTX2Prompt

- **Category:** text
- **Documented:** No

---

### TextOverlay

- **Category:** text
- **Documented:** No

---

### TextToLowercase

- **Category:** text
- **Documented:** No

---

### TextToUppercase

- **Category:** text
- **Documented:** No

---

### ThresholdMask

- **Category:** image/mask
- **Documented:** No

---

### TomePatchModel

- **Category:** model/patch/unet
- **Documented:** No

---

### TopazImageEnhance

- **Category:** partner/image/Topaz
- **Documented:** No

---

### TopazImageEnhanceV2

- **Category:** partner/image/Topaz
- **Documented:** No

---

### TopazVideoEnhance

- **Category:** partner/video/Topaz
- **Documented:** No

---

### TopazVideoEnhanceV2

- **Category:** partner/video/Topaz
- **Documented:** No

---

### TorchCompileModel

- **Category:** experimental
- **Documented:** No

---

### TrainLoraNode

- **Category:** model/training
- **Documented:** No

---

### TransformSplat

- **Category:** 3d/splat
- **Documented:** No

---

### Trellis2Conditioning

- **Category:** model/conditioning/trellis2
- **Documented:** No

---

### Trellis2ShapeStage

- **Category:** model/conditioning/trellis2
- **Documented:** No

---

### Trellis2TextureStage

- **Category:** model/conditioning/trellis2
- **Documented:** No

---

### Trellis2UpsampleStage

- **Category:** model/conditioning/trellis2
- **Documented:** No

---

### TrimAudioDuration

- **Category:** audio
- **Documented:** No

---

### TrimVideoLatent

- **Category:** model/latent
- **Documented:** No

---

### TripleCLIPLoader

- **Category:** model/loaders
- **Documented:** No

---

### TripoConversionNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoEditMultiviewNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoImageToModelNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoImageToMultiviewNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoImportModelNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoMeshCompleteNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoMultiviewToModelNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoP1ImageToModelNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoP1MultiviewToModelNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoP1TextToModelNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoRetargetNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoRetopologyNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoRigCheckNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoRigNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoSegmentNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoSplatConditioning

- **Category:** model/conditioning/triposplat
- **Documented:** No

---

### TripoSplatPreprocessImage

- **Category:** model/conditioning/triposplat
- **Documented:** No

---

### TripoSplatSamplingPreview

- **Category:** model/latent/triposplat
- **Documented:** No

---

### TripoTextToModelNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TripoTextureNode

- **Category:** partner/3d/Tripo
- **Documented:** No

---

### TruncateText

- **Category:** text
- **Documented:** No

---

### UNETLoader

- **Category:** model/loaders
- **Documented:** No

---

### UNetCrossAttentionMultiply

- **Category:** experimental/attention_experiments
- **Documented:** No

---

### UNetSelfAttentionMultiply

- **Category:** experimental/attention_experiments
- **Documented:** No

---

### UNetTemporalAttentionMultiply

- **Category:** experimental/attention_experiments
- **Documented:** No

---

### USOStyleReference

- **Category:** model/patch/flux
- **Documented:** No

---

### UnwrapMesh

- **Category:** 3d/texturing
- **Documented:** No

---

### UpscaleModelLoader

- **Category:** model/loaders
- **Documented:** No

---

### VAEDecode

- **Category:** model/latent
- **Documented:** No

---

### VAEDecodeAudio

- **Category:** model/latent
- **Documented:** No

---

### VAEDecodeAudioTiled

- **Category:** model/latent
- **Documented:** No

---

### VAEDecodeHunyuan3D

- **Category:** model/latent/hunyuan 3d
- **Documented:** No

---

### VAEDecodeTiled

- **Category:** model/latent
- **Documented:** No

---

### VAEDecodeTripoSplat

- **Category:** model/latent/triposplat
- **Documented:** No

---

### VAEEncode

- **Category:** model/latent
- **Documented:** No

---

### VAEEncodeAudio

- **Category:** model/latent
- **Documented:** No

---

### VAEEncodeForInpaint

- **Category:** model/latent
- **Documented:** No

---

### VAEEncodeTiled

- **Category:** model/latent
- **Documented:** No

---

### VAELoader

- **Category:** model/loaders
- **Documented:** No

---

### VAESave

- **Category:** model/merging
- **Documented:** No

---

### VOIDInpaintConditioning

- **Category:** model/conditioning/void
- **Documented:** No

---

### VOIDQuadmaskPreprocess

- **Category:** image/mask
- **Documented:** No

---

### VOIDSampler

- **Category:** model/sampling/samplers
- **Documented:** No

---

### VOIDWarpedNoise

- **Category:** model/latent/void
- **Documented:** No

---

### VOIDWarpedNoiseSource

- **Category:** model/latent/void
- **Documented:** No

---

### VPScheduler

- **Category:** model/sampling/schedulers
- **Documented:** No

---

### VaeDecodeShapeTrellis

- **Category:** model/latent/trellis
- **Documented:** No

---

### VaeDecodeStructureTrellis2

- **Category:** model/latent/trellis
- **Documented:** No

---

### VaeDecodeTextureTrellis

- **Category:** model/latent/trellis
- **Documented:** No

---

### Veo3FirstLastFrameNode

- **Category:** partner/video/Veo
- **Documented:** No

---

### Veo3VideoGenerationNode

- **Category:** partner/video/Veo
- **Documented:** No

---

### Video Slice

- **Category:** video
- **Documented:** No

---

### Video To Blob Node

- **Category:** RequestNode/Converters
- **Documented:** Yes

**Purpose:** Конвертирует Comfyui VIDEO → байты (MP4/GIF)

**Required Inputs:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| video | VIDEO |  | Видео ComfyUI |

**Outputs:**
- `video_bytes` (BYTES): Байты видео
- `frame_count` (INT): Количество кадров

**Related:** Blob To Video Node

---

### VideoFrameSample

- **Category:** video
- **Documented:** No

---

### VideoLinearCFGGuidance

- **Category:** model/sampling/guiders
- **Documented:** No

---

### VideoRandomTemporalCrop

- **Category:** video/transform
- **Documented:** No

---

### VideoTemporalCrop

- **Category:** video/transform
- **Documented:** No

---

### VideoTriangleCFGGuidance

- **Category:** model/sampling/guiders
- **Documented:** No

---

### Vidu2ImageToVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### Vidu2ReferenceVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### Vidu2StartEndToVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### Vidu2TextToVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### Vidu3ImageToVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### Vidu3StartEndToVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### Vidu3TextToVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### ViduExtendVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### ViduImageToVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### ViduMultiFrameVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### ViduReferenceVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### ViduStartEndToVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### ViduTextToVideoNode

- **Category:** partner/video/Vidu
- **Documented:** No

---

### VoxelToMesh

- **Category:** 3d
- **Documented:** No

---

### VoxelToMeshBasic

- **Category:** 3d
- **Documented:** No

---

### Wan22FunControlToVideo

- **Category:** model/conditioning/wan/fun control
- **Documented:** No

---

### Wan22ImageToVideoLatent

- **Category:** model/conditioning/wan
- **Documented:** No

---

### Wan2ImageToVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### Wan2ReferenceVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### Wan2TextToVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### Wan2VideoContinuationApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### Wan2VideoEditApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### Wan3ImageToVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### Wan3ReferenceToVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### WanAnimate2Cache

- **Category:** model/conditioning/wan/animate
- **Documented:** No

---

### WanAnimate2ToVideo

- **Category:** model/conditioning/wan/animate
- **Documented:** No

---

### WanAnimateToVideo

- **Category:** model/conditioning/wan/animate
- **Documented:** No

---

### WanCameraEmbedding

- **Category:** model/conditioning/wan/camera
- **Documented:** No

---

### WanCameraImageToVideo

- **Category:** model/conditioning/wan/camera
- **Documented:** No

---

### WanContextWindowsManual

- **Category:** model/patch/wan
- **Documented:** No

---

### WanDancerEncodeAudio

- **Category:** model/conditioning/wan/dancer
- **Documented:** No

---

### WanDancerPadKeyframes

- **Category:** image/video
- **Documented:** No

---

### WanDancerPadKeyframesList

- **Category:** image/video
- **Documented:** No

---

### WanDancerVideo

- **Category:** model/conditioning/wan/dancer
- **Documented:** No

---

### WanFirstLastFrameToVideo

- **Category:** model/conditioning/wan
- **Documented:** No

---

### WanFunControlToVideo

- **Category:** model/conditioning/wan/fun control
- **Documented:** No

---

### WanFunInpaintToVideo

- **Category:** model/conditioning/wan/fun inpaint
- **Documented:** No

---

### WanHuMoImageToVideo

- **Category:** model/conditioning/wan/humo
- **Documented:** No

---

### WanImageToImageApi

- **Category:** partner/image/Wan
- **Documented:** No

---

### WanImageToVideo

- **Category:** model/conditioning/wan
- **Documented:** No

---

### WanImageToVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### WanInfiniteTalkToVideo

- **Category:** model/conditioning/wan/infinite talk
- **Documented:** No

---

### WanMoveConcatTrack

- **Category:** model/conditioning/wan/move
- **Documented:** No

---

### WanMoveTrackToVideo

- **Category:** model/conditioning/wan/move
- **Documented:** No

---

### WanMoveTracksFromCoords

- **Category:** model/conditioning/wan/move
- **Documented:** No

---

### WanMoveVisualizeTracks

- **Category:** model/conditioning/wan/move
- **Documented:** No

---

### WanPhantomSubjectToVideo

- **Category:** model/conditioning/wan/phantom subject
- **Documented:** No

---

### WanReferenceVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### WanSCAILToVideo

- **Category:** model/conditioning/wan/scail
- **Documented:** No

---

### WanSoundImageToVideo

- **Category:** model/conditioning/wan/sound
- **Documented:** No

---

### WanSoundImageToVideoExtend

- **Category:** model/conditioning/wan/sound
- **Documented:** No

---

### WanTextToImageApi

- **Category:** partner/image/Wan
- **Documented:** No

---

### WanTextToVideoApi

- **Category:** partner/video/Wan
- **Documented:** No

---

### WanTrackToVideo

- **Category:** model/conditioning/wan/move
- **Documented:** No

---

### WanUni3CControlnetApply

- **Category:** model/patch/wan
- **Documented:** No

---

### WanVaceToVideo

- **Category:** model/conditioning/wan/vace
- **Documented:** No

---

### WavespeedFlashVSRNode

- **Category:** partner/video/WaveSpeed
- **Documented:** No

---

### WavespeedImageUpscaleNode

- **Category:** partner/image/WaveSpeed
- **Documented:** No

---

### WebcamCapture

- **Category:** image
- **Documented:** No

---

### WeldVertices

- **Category:** 3d/mesh
- **Documented:** No

---

### ZImageFunControlnet

- **Category:** model/patch/z-image
- **Documented:** No

---

### unCLIPCheckpointLoader

- **Category:** model/loaders
- **Documented:** No

---

### unCLIPConditioning

- **Category:** model/conditioning
- **Documented:** No

---

### wanBlockSwap

- **Category:** 
- **Documented:** No

---
