"""Patch the installed source bridge/extension with backups; no dependency install."""
import argparse,datetime,hashlib,json,pathlib,re,shutil,subprocess

def install(profile,workspace,home,activate=False):
    assets=pathlib.Path(__file__).resolve().parents[1]/'browser-adapter'
    backup=profile/'backups'/('video-companion-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'));backup.mkdir(parents=True)
    edits=[]
    def write(path,text):
        if path.exists():shutil.copy2(path,backup/(str(len(edits))+'-'+path.name))
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8');edits.append(str(path))
    def patch(path,old,new):
        text=path.read_text(encoding='utf-8')
        if new in text:return
        if text.count(old)!=1:raise RuntimeError('Unexpected source version: '+str(path)+' / '+old[:60])
        write(path,text.replace(old,new))
    for bridge in [profile/'.dsh-browser-source',workspace/'packages/browser/bridge-browser']:
        write(bridge/'src/companion.ts',(assets/'companion.ts').read_text(encoding='utf-8'))
        write(bridge/'tests/companion.spec.ts',(assets/'companion.spec.ts').read_text(encoding='utf-8'))
        patch(bridge/'src/index.ts',"import { BridgeServer } from './server.ts'","import { BridgeServer } from './server.ts'\nimport { registerVideoCompanion } from './companion.ts'")
        patch(bridge/'src/index.ts',"export const inject = ['webServer', 'typertGateway', 'connection', 'tools', 'agents']","export const inject = ['webServer', 'typertGateway', 'connection', 'tools', 'agents', 'llm', 'attachments']")
        entry=bridge/'src/index.ts'
        text=entry.read_text(encoding='utf-8')
        previous="return () => { disposeCompanion(); for (const dispose of disposers.values()) dispose() }"
        current="return async () => { await disposeCompanion(); for (const dispose of disposers.values()) dispose() }"
        if previous in text:write(entry,text.replace(previous,current))
        patch(entry,"return () => { for (const dispose of disposers.values()) dispose() }",'const disposeCompanion = registerVideoCompanion(ctx, server, '+json.dumps(str(home).replace('\\','/'))+")\n    "+current)
    extension=workspace/'extensions/dsh-browser'
    write(extension/'src/content/video.ts',(assets/'video.ts').read_text(encoding='utf-8'))
    write(extension/'tests/video.spec.ts',(assets/'video.spec.ts').read_text(encoding='utf-8'))
    write(extension/'tests/video-authorization.spec.ts',(assets/'video-authorization.spec.ts').read_text(encoding='utf-8'))
    write(extension/'src/background/video-grants.ts',(assets/'video-grants.ts').read_text(encoding='utf-8'))
    write(extension/'tests/video-grants.spec.ts',(assets/'video-grants.spec.ts').read_text(encoding='utf-8'))
    patch(extension/'src/content/actions.ts',"import { clickTargetsByText, pageText, truncate } from './extract.ts'","import { clickTargetsByText, pageText, truncate } from './extract.ts'\nimport { videoAction } from './video.ts'")
    patch(extension/'src/content/actions.ts',"switch (action) {","switch (action) {\n    case 'browser_video_info':\n    case 'browser_capture_video':\n      return videoAction(action, args)")
    path=extension/'src/background/authorization.ts'
    patch(path,"new Set(['browser_snapshot', 'browser_get_text'])","new Set(['browser_snapshot', 'browser_get_text', 'browser_video_info', 'browser_capture_video'])")
    before=path.read_text(encoding='utf-8')
    old="summary: call.name === 'browser_capture_video'\n        ? localized(locale, 'Read the current video and audio window for the companion', '读取当前视频画面和音频供陪看理解')"
    consent="summary: call.name === 'browser_capture_video' || call.args.watchConsent === true\n        ? localized(locale, 'Read this video and audio during this companion session; ends on stop or navigation', '在本次陪看中持续读取当前视频画面和音频，停止或离开页面时结束')"
    if old in before:write(path,before.replace(old,consent))
    patch(path,"summary: call.name === 'browser_snapshot'",consent+"\n        : call.name === 'browser_video_info'\n          ? localized(locale, 'Read the current video playback state', '读取当前视频播放状态')\n          : call.name === 'browser_snapshot'")
    path=extension/'src/background/tools.ts'
    patch(path,"import { wrapUntrustedContent } from '../security/untrusted.ts'", "import { wrapUntrustedContent } from '../security/untrusted.ts'\nimport { isCompanionRead, hasVideoGrant, grantVideoRead, releaseVideoGrant } from './video-grants.ts'")
    patch(path,"(call.name === 'browser_snapshot' || call.name === 'browser_get_text'))", "(['browser_snapshot', 'browser_get_text', 'browser_video_info', 'browser_capture_video'].includes(call.name)))")
    patch(path,"const text = answerText(response)","if (call.name === 'browser_video_info' || call.name === 'browser_capture_video') return response\n  const text = answerText(response)")
    patch(path,"if (call.name === 'browser_open_tab') {\n    return unavailable('browser_open_tab must be dispatched through the background open-tab path.')", "if (call.name === 'browser_video_release') {\n    releaseVideoGrant(call)\n    return { ok: true, result: { text: 'Companion read consent released.' } }\n  }\n  if (call.name === 'browser_open_tab') {\n    return unavailable('browser_open_tab must be dispatched through the background open-tab path.')")
    patch(path,"  const approval = tabManagement.unrestrictedAccess\n    ? undefined\n    : approvalPromptForCall(call, sharePageContent, frames)", "  const companionRead = isCompanionRead(call)\n  const companionGranted = companionRead && hasVideoGrant(call, tab.id, frames)\n  if (companionRead && !tabManagement.unrestrictedAccess && sharePageContent === 'ask' && !companionGranted && call.args.watchConsent !== true) return unavailable('Companion consent expired after the page or tab changed; start watching again.')\n  const approval = tabManagement.unrestrictedAccess || companionGranted\n    ? undefined\n    : approvalPromptForCall(call, sharePageContent, frames)")
    patch(path,"(approval.kind === 'action' && !sameTargetDocument(call, frames, executionFrames))", "((approval.kind === 'action' || companionRead) && !sameTargetDocument(call, frames, executionFrames))")
    patch(path,"  if (!isInjectablePage(tab.url)) {\n    return await dispatchTabNativeTool", "  if (companionRead && call.args.watchConsent === true && approval !== undefined) grantVideoRead(call, tab.id, executionFrames)\n  if (!isInjectablePage(tab.url)) {\n    return await dispatchTabNativeTool")
    # Make the companion tool visible wherever the existing video group is selected.
    policy=profile/'vendor/dsh-mode-profiles-video-v1/tool-policy.mjs'
    patch(policy,"prefixes:['mcp__video__']}","prefixes:['mcp__video__'],names:['browser_watch_video']}")
    guidance=profile/'vendor/dsh-mode-profiles-video-v1/video-guidance.mjs'
    text=(assets/'guidance.mjs').read_text(encoding='utf-8');write(guidance,text)
    if activate:
        pnpm=shutil.which('pnpm')
        if not pnpm:raise RuntimeError('pnpm is required to build the already-installed browser workspace')
        for directory in [profile/'.dsh-browser-source',extension]:
            subprocess.run([pnpm,'run','build'],cwd=directory,check=True)
        target=pathlib.Path.home()/'.dsh/browser-extension'
        for name in ['background.js','content.js']:
            source=extension/'dist'/name
            if (target/name).exists():shutil.copy2(target/name,backup/('extension-'+name))
            shutil.copy2(source,target/name)
        # New filenames force a fresh module instance in the existing desktop
        # host; dependencies remain alongside the original built entry.
        built=profile/'.dsh-browser-source/lib/index.js'
        digest=hashlib.sha256(built.read_bytes()).hexdigest()[:12]
        fresh=built.with_name('index-video-'+digest+'.js');shutil.copy2(built,fresh)
        guide=guidance.with_name('video-guidance-'+hashlib.sha256(guidance.read_bytes()).hexdigest()[:12]+'.mjs');shutil.copy2(guidance,guide)
        config=profile/'cordis.patch.yml';content=config.read_text(encoding='utf-8')
        pattern=r'(?m)^(\s*- id: local-video-guidance\r?\n\s*name: )[^\r\n]+'
        content,count=re.subn(pattern,lambda m:m[1]+json.dumps(guide.as_uri()),content)
        if count!=1:raise RuntimeError('Expected exactly one existing local-video-guidance entry')
        override='- id: bridge-browser\n  name: '+json.dumps(fresh.as_uri())
        pattern=r'(?m)^- id: bridge-browser\r?\n  name: [^\r\n]+'
        if re.search(pattern,content):content=re.sub(pattern,lambda _:override,content)
        else:content+='\n# Current-player video companion\n'+override+'\n'
        write(config,content)
    (backup/'manifest.json').write_text(json.dumps({'changed':edits},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Source adapter installed. Backup:',backup)
    print('Activated; an already-open browser must reload its existing DSH extension.' if activate else 'Build the profile bridge and extension with their existing pnpm scripts before activation.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profile',type=pathlib.Path,default=pathlib.Path.home()/'.dsh/profiles/desktop');p.add_argument('--workspace',type=pathlib.Path,default=pathlib.Path.home()/'.dsh/dsh-browser');p.add_argument('--home',required=True,type=pathlib.Path);p.add_argument('--activate',action='store_true');a=p.parse_args();install(a.profile.resolve(),a.workspace.resolve(),a.home.resolve(),a.activate)
