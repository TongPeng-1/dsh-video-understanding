import pathlib,sys,torch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from dsh_video_mcp.videochat3_compat import partitioned_vision_attention

def check(device,dtype):
    torch.manual_seed(42)
    for lengths in ([3,5,2],[1,1,1],[17],[13,17,2]):
        n=sum(lengths);q,k,v=[torch.randn(n,4,64,device=device,dtype=dtype) for _ in range(3)]
        bounds=torch.tensor([0]+list(torch.tensor(lengths).cumsum(0).tolist()),device=device)
        mask=torch.zeros(1,n,n,device=device,dtype=torch.bool)
        for a,b in zip(bounds.tolist(),bounds.tolist()[1:]):mask[:,a:b,a:b]=True
        expected=torch.nn.functional.scaled_dot_product_attention(q.transpose(0,1),k.transpose(0,1),v.transpose(0,1),mask,dropout_p=0.0).transpose(0,1).reshape(n,-1)
        actual=partitioned_vision_attention(q,k,v,bounds,bounds)
        torch.testing.assert_close(actual,expected,atol=.015625 if dtype==torch.bfloat16 else 1e-6,rtol=.02 if dtype==torch.bfloat16 else 1e-5)
    print('PASS original dense block mask equivalence:',device,dtype)
check('cpu',torch.float32)
if torch.cuda.is_available():check('cuda',torch.bfloat16)
