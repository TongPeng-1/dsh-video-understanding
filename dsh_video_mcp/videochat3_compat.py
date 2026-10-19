"""Adapters for pinned 4.x model code on Transformers 5.10.4."""
from types import MethodType


def tie_checkpoint_output(model,loading_info):
    missing=set(loading_info.get('missing_keys',[]))
    if missing-{'lm_head.weight'} or loading_info.get('mismatched_keys') or loading_info.get('unexpected_keys') or loading_info.get('error_msgs'):
        raise RuntimeError('VideoChat3 checkpoint did not load exactly: '+str(loading_info))
    if not model.config.text_config.tie_word_embeddings:
        raise RuntimeError('Pinned VideoChat3 checkpoint must use tied text embeddings')
    # The upstream checkpoint omits lm_head and declares tied embeddings. 5.x
    # no longer infers this relationship from its old list-style declaration.
    model.lm_head.weight=model.get_input_embeddings().weight


def generation_inputs(model,input_ids,base_prepare,past_key_values=None,**kwargs):
    result=base_prepare(model,input_ids,past_key_values=past_key_values,**kwargs)
    # 5.x omits absent inputs_embeds; the upstream override indexes it directly.
    if past_key_values is not None and past_key_values.get_seq_length()>0:
        result['pixel_values']=None;result['pixel_values_videos']=None
    return result


def install_generation_compatibility(model):
    from transformers.generation.utils import GenerationMixin
    def prepare(self,input_ids,past_key_values=None,**kwargs):
        return generation_inputs(self,input_ids,GenerationMixin.prepare_inputs_for_generation,past_key_values,**kwargs)
    model.prepare_inputs_for_generation=MethodType(prepare,model)


def partitioned_vision_attention(q,k,v,q_cu_seqlens=None,k_cu_seqlens=None):
    """Equivalent block-diagonal self-attention without the dense global mask."""
    import torch
    from torch.nn.functional import scaled_dot_product_attention
    q_bounds=q_cu_seqlens.tolist();k_bounds=k_cu_seqlens.tolist()
    if q_bounds!=k_bounds or q.shape[0]!=k.shape[0] or q_bounds[0]!=0 or q_bounds[-1]!=q.shape[0]:
        raise ValueError('Unexpected VideoChat3 vision attention partition')
    outputs=[]
    for start,end in zip(q_bounds,q_bounds[1:]):
        if end<=start:continue
        qs=q[start:end].transpose(0,1).unsqueeze(0)
        ks=k[start:end].transpose(0,1).unsqueeze(0)
        vs=v[start:end].transpose(0,1).unsqueeze(0)
        out=scaled_dot_product_attention(qs,ks,vs,dropout_p=0.0)
        outputs.append(out.squeeze(0).transpose(0,1))
    return torch.cat(outputs,dim=0).reshape(q.shape[0],-1)


def install_vision_attention(model):
    import sys
    module=sys.modules[model.__class__.__module__]
    module.VL_VISION_ATTENTION_FUNCTIONS['sdpa']=partitioned_vision_attention


def prepare_checkpoint_class(model_class,config):
    if not config.text_config.tie_word_embeddings:
        raise RuntimeError('Pinned checkpoint requires tied text embeddings')
    config.tie_word_embeddings=True
    model_class._tied_weights_keys={'lm_head.weight':'model.language_model.embed_tokens.weight'}


def caption_stop_reason(text):
    import re
    stripped=text.strip()
    if len(stripped)>=4 and (any(ch in stripped for ch in '。！？\n') or re.search(r'[.!?](?:\s|$)',stripped)):
        return 'sentence'
    if len(stripped)>=48:return 'character_budget'
    return None


def install_presampled_video_processor(processor):
    """Bridge upstream 4.x video preprocessing for our already sampled RGB tensors.

    Use the pinned model's normalization/patch layout directly: Transformers 5's
    generic kwargs validator is incompatible with this remote processor's schema.
    This deliberately accepts only the runner's in-memory, pre-resized path.
    """
    from types import MethodType
    def preprocess(vp,videos,**kwargs):
        if kwargs.get('do_resize') is not False or kwargs.get('do_sample_frames') is not False:
            raise ValueError('VideoChat3 adapter requires pre-resized, pre-sampled video')
        if not isinstance(videos,list) or not videos or any(
            v.ndim!=4 or v.shape[1]!=3 or v.shape[2]%28 or v.shape[3]%28 for v in videos
        ):
            raise ValueError('Expected RGB TCHW tensors with dimensions divisible by 28')
        videos,metadata=vp._decode_and_sample_videos(videos,kwargs['video_metadata'],False)
        result=vp._preprocess(videos,do_resize=False,do_convert_rgb=True,
            do_rescale=True,rescale_factor=1/255.,do_normalize=True,
            image_mean=vp.image_mean,image_std=vp.image_std,patch_size=vp.patch_size,
            temporal_patch_size=vp.temporal_patch_size,merge_size=vp.merge_size,
            return_tensors='pt')
        result['video_metadata']=metadata
        return result
    processor.video_processor.preprocess=MethodType(preprocess,processor.video_processor)


def process_performance_state():
    import ctypes,os
    if os.name!='nt':return {}
    from ctypes import wintypes
    class State(ctypes.Structure):
        _fields_=[('Version',wintypes.ULONG),('ControlMask',wintypes.ULONG),('StateMask',wintypes.ULONG)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.GetProcessInformation.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    state=State(1,0,0)
    ok=kernel.GetProcessInformation(kernel.GetCurrentProcess(),4,ctypes.byref(state),ctypes.sizeof(state))
    return {'power_throttling_control':state.ControlMask,'power_throttling_state':state.StateMask} if ok else {'power_query_error':ctypes.get_last_error()}


def configure_process_performance():
    """Request foreground QoS and usable timers for this inference process only."""
    import atexit,ctypes,os
    if os.name!='nt':return {}
    from ctypes import wintypes
    class State(ctypes.Structure):
        _fields_=[('Version',wintypes.ULONG),('ControlMask',wintypes.ULONG),('StateMask',wintypes.ULONG)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.SetProcessInformation.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    # EXECUTION_SPEED (1) and IGNORE_TIMER_RESOLUTION (4), both explicitly off.
    state=State(1,5,0)
    ok=kernel.SetProcessInformation(kernel.GetCurrentProcess(),4,ctypes.byref(state),ctypes.sizeof(state))
    result={'qos_request_ok':bool(ok)}
    if not ok:result['qos_request_error']=ctypes.get_last_error()
    winmm=ctypes.WinDLL('winmm');period=winmm.timeBeginPeriod(1);result['timer_period_result']=period
    if period==0:atexit.register(lambda:winmm.timeEndPeriod(1))
    return result
