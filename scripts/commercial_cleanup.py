"""Version-pinned commercial entry cleanup. Input and voice cores are untouched."""
import re

# Keep shared infrastructure needed by the input service and local clipboard/menu.
LOCAL_LIFECYCLES = (
    'com/baidu/input/AppApplicationLifecycleCallbacks',
    'com/baidu/input/ImeApplicationLifecycleCallbacks',
    'com/baidu/input/clipboard/ClipboardAppLifecycleCallback',
    'com/baidu/input/ime/logo/base/LogoMenuAppLifecycleCallback',
)

DISABLED_PREFIXES = (
    'com.baidu.sofire.', 'com.qq.e.', 'com.bytedance.sdk.openadsdk.', 'com.byazt.',
    'com.baidu.android.pushservice.', 'com.baidu.pushservice.', 'com.xiaomi.push.',
    'com.xiaomi.mipush.', 'com.vivo.push.', 'com.heytap.msp.push.', 'com.meizu.cloud.pushsdk.',
    'com.huawei.hms.support.api.push.', 'com.huawei.hms.aaid.', 'com.huawei.agconnect.',
    'com.baidu.input.push.', 'com.baidu.videoads.', 'com.yj.inner.', 'com.stars.era.',
    'com.baidu.input.ad.', 'com.baidu.input.megsplashad.', 'com.baidu.input.goods.',
    'com.baidu.input.imemember.', 'com.baidu.input.aicard.', 'com.baidu.input.platochat.',
    'com.baidu.input.wallpaper.', 'com.baidu.input.shortcut.', 'com.baidu.input.switchguide.',
    'com.baidu.input.meeting.', 'com.baidu.input.ime.front.note.', 'com.baidu.acs.',
    'com.baidu.nadcore.', 'com.baidu.searchbox.', 'com.baidu.sapi2.', 'com.sina.weibo.',
    'com.baidu.cesium.', 'com.baidu.android.common.util.GalaxyProvider',
    'com.baidu.input.shop.', 'com.baidu.input.shopbase.', 'com.baidu.input.layout.store.',
    'com.baidu.input.account.', 'com.baidu.input.sync.', 'com.baidu.input.wxapi.',
    'com.baidu.input.svip.', 'com.baidu.input.pocketdocs.', 'com.baidu.input.inspiration_corpus.shop.',
    'com.baidu.input.aifontwriting.', 'com.baidu.input.paperwriting.', 'com.baidu.input.aiavatar.',
    'com.baidu.input.aicreation.', 'com.baidu.input.aidiyskin.', 'com.baidu.input.appranker.',
    'com.baidu.input.adlandingpage.', 'com.baidu.input.rewardvideo.', 'com.baidu.input.mobsdk.',
    'com.baidu.input.service_distrubute.', 'com.baidu.input.textchain.', 'com.baidu.input.pointswall.',
    'com.baidu.input.circle.', 'com.baidu.input.circleapp.', 'com.baidu.input.ocrapiimpl.',
    'com.baidu.input.thirdservice.', 'com.baidu.input.feedback.', 'com.baidu.input.talos.',
)

LOCAL_PERMISSIONS = frozenset((
    'android.permission.RECORD_AUDIO', 'android.permission.MODIFY_AUDIO_SETTINGS',
    'android.permission.VIBRATE', 'android.permission.WAKE_LOCK',
    'android.permission.ACCESS_NETWORK_STATE',
    'android.permission.BLUETOOTH', 'android.permission.BLUETOOTH_CONNECT',
    'android.permission.FOREGROUND_SERVICE', 'android.permission.FOREGROUND_SERVICE_MICROPHONE',
    'android.permission.READ_EXTERNAL_STORAGE', 'android.permission.WRITE_EXTERNAL_STORAGE',
    'com.baidu.input.permission.REGISTERRECEIVE',
    'com.baidu.input.permission.SEND', 'com.baidu.input.permission.RECEIVE',
    'com.baidu.input.permission.PLUGININTERFACESERVICE',
))


def patch(source, replace, texts, patches):
    # Keep the vendor's local preference storage and change listeners intact.
    cls = 'com/baidu/input/pref/PreferenceHandler'
    text = source(cls)
    pattern = r'(?m)(^\.method public final g\(B\)V\n[\s\S]*?)(^\.end method)'
    def filter_settings(match):
        body = match[1]
        assert body.count('    return-void') == 1
        assert '    .locals 7\n' in body
        # The original method reuses both parameter registers on some branches.
        body = body.replace('    .locals 7\n', '''    .locals 9
    iget-object v7, p0, Lcom/baidu/input/pref/PreferenceHandler;->b:Landroid/preference/PreferenceActivity;
    move v8, p1
''', 1)
        return body.replace('    return-void', '''    invoke-static {v7, v8}, Llocal/baiduoffline/OfflineSettings;->filter(Landroid/preference/PreferenceActivity;I)V
    return-void''') + match[2]
    text, count = re.subn(pattern, filter_settings, text)
    assert count == 1, 'Settings builder anchor changed'
    texts[cls] = text
    patches.append({'class': cls, 'method': 'g', 'purpose': 'Retain local input preferences and remove online entries'})
    replace('com/baidu/input/ImeMainConfigActivity', 'onCreateOptionsMenu(Landroid/view/Menu;)Z',
            '    .locals 1\n    const/4 v0, 0x0\n    return v0')
    replace('com/baidu/input/ImeMainConfigActivity', 'b()V', '    .locals 0\n    return-void')

    body = ['    .locals 2', '    new-instance v0, Ljava/util/ArrayList;',
            '    invoke-direct {v0}, Ljava/util/ArrayList;-><init>()V']
    for cls in LOCAL_LIFECYCLES:
        body.extend((f'    new-instance v1, L{cls};',
                     f'    invoke-direct {{v1}}, L{cls};-><init>()V',
                     '    invoke-virtual {v0, v1}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z'))
    body.append('    return-object v0')
    replace('com/baidu/input/IImeApplicationLifecycleCallbacks_LifecycleComponent_ListProvider',
            'get()Ljava/lang/Object;', '\n'.join(body))
    # The remote plugin cloud-control task can also be scheduled by shared startup.
    replace('com/baidu/searchbox/cloudcontrol/CloudControlManager$1', 'run()V',
            '    .locals 0\n    return-void')

    # The AI font observer is registered separately from application startup.
    # Disable its callbacks together with FontAiImeApplicationLifecycleCallbacks.
    for signature in ('onDestroy()V', 'onInitFinish(Landroid/view/inputmethod/EditorInfo;Z)V',
                      'onStartInputView(Landroid/view/inputmethod/EditorInfo;Z)V',
                      'onWindowHidden()V', 'onWindowShown()V'):
        replace('com/baidu/input/aifont/base/AiFontObserver', signature, '    .locals 0\n    return-void')

    for signature, helper in (
        ('c()Ljava/util/List;', 'toolbar'), ('d()Ljava/util/List;', 'toolbar'),
        ('f()Ljava/util/ArrayList;', 'toolbar'), ('g()Ljava/util/List;', 'menu'),
        ('e()Ljava/util/ArrayList;', 'menu'),
    ):
        replace('com/baidu/input/menutoolimpl/Data', signature,
                '    .locals 1\n    invoke-static {}, Llocal/baiduoffline/OfflineMenus;->' + helper +
                '()Ljava/util/ArrayList;\n    move-result-object v0\n    return-object v0')

    # This second list builder normally appends an AI text action after the toolbar.
    replace('com/baidu/input/ime/reconstruction/data/flaucher/FlauncherFunctionImplByMenuTool',
            'a()Ljava/util/List;', '    .locals 1\n    invoke-static {}, Llocal/baiduoffline/OfflineMenus;->codes()Ljava/util/ArrayList;\n    move-result-object v0\n    return-object v0')
    replace('com/baidu/input/ime/aitextorganize/CandTextOrganizeController', 'o()Z',
            '    .locals 1\n    const/4 v0, 0x0\n    return v0')
    # The built-in skin has a separate F173 AI button outside the configurable bar.
    replace('com/baidu/input/aicard/impl/AICardImpl', 'Vc()Z',
            '    .locals 1\n    const/4 v0, 0x0\n    return v0')

    replace('com/baidu/input/ime/logo/manager/MenuDataProvider', 'a()V', '''    .locals 2
    const/4 v0, 0x0
    iput-boolean v0, p0, Lcom/baidu/input/ime/logo/manager/MenuDataProvider;->b:Z
    iget-object v0, p0, Lcom/baidu/input/ime/logo/manager/MenuDataProvider;->a:Ljava/util/ArrayList;
    invoke-virtual {v0}, Ljava/util/ArrayList;->clear()V
    invoke-static {}, Llocal/baiduoffline/OfflineMenus;->rows()Ljava/util/ArrayList;
    move-result-object v1
    invoke-virtual {v0, v1}, Ljava/util/ArrayList;->addAll(Ljava/util/Collection;)Z
    return-void''')

    # Clipboard has a separate cloud action, outside the main keyboard menu.
    # Keep its view object for layout compatibility, but do not attach its button.
    cls = 'com/baidu/input/inspirationcorpus/common/view/bottom/InspirationCorpusBottomNavView'
    text = source(cls)
    anchor = '    invoke-virtual {v14, v6}, Landroid/view/ViewGroup;->addView(Landroid/view/View;)V'
    assert text.count(anchor) == 1, 'Clipboard sync button anchor changed'
    texts[cls] = text.replace(anchor, '    # Omit cloud synchronization button.\n    nop')
    patches.append({'class': cls, 'method': '<init>', 'purpose': 'Remove clipboard cloud sync button'})
    replace(cls, 'j(I)V', '    .locals 0\n    return-void')
    replace(cls + '$5', 'a()V', '    .locals 0\n    return-void')
    cls = 'com/baidu/input/clipboard/panel/view/ClipboardPanelViewImpl'
    replace(cls, 'onSyncIconClicked()Z', '    .locals 1\n    const/4 v0, 0x1\n    return v0')
    replace(cls, 'access$openCloudSyncSettings(Lcom/baidu/input/clipboard/panel/view/ClipboardPanelViewImpl;)V',
            '    .locals 0\n    return-void')
    for signature in ('onSearchIconClicked(I)V', 'onTranslateIconClicked(I)V'):
        replace(cls, signature, '    .locals 0\n    return-void')

    # Item actions use web search/translation, unlike the bottom local search.
    cls = 'com/baidu/input/clipboard/panel/view/viewholder/ClipboardViewHolder'
    text = source(cls)
    for line in (334, 354):
        anchor = f'    .line {line}\n    invoke-virtual {{v4, v6}}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z'
        assert text.count(anchor) == 1, 'Clipboard online item action anchor changed'
        text = text.replace(anchor, '    # Omit online clipboard item action.\n    nop')
    texts[cls] = text
    patches.append({'class': cls, 'method': '<init>', 'purpose': 'Remove web search and online translation actions'})

    # Keep clipboard and local phrases, omit the online recommendation tab.
    cls = 'com/baidu/input/inspiration_corpus/panel/presenter/InspirationPanelViewPresenterImpl'
    body = ['    .locals 1']
    for tab in ('clipboard', 'mine'):
        tab_cls = cls + '$createDefaultTabs$' + tab + '$1'
        body.extend((f'    new-instance v0, L{tab_cls};',
                     f'    invoke-direct {{v0}}, L{tab_cls};-><init>()V',
                     '    invoke-virtual {p0, v0}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z'))
    body.append('    return-void')
    replace(cls, 'c(Ljava/util/ArrayList;)V', '\n'.join(body))
    replace(cls, 'e(Lkotlin/coroutines/jvm/internal/ContinuationImpl;)Ljava/lang/Object;',
            '    .locals 1\n    sget-object v0, Lkotlin/Unit;->a:Lkotlin/Unit;\n    return-object v0')

    cls = 'com/baidu/input/inspiration_corpus/panel/view/InspirationCorpusPanelView'
    text = source(cls)
    pattern = r'(?m)(^\.method public setTabList\(ILjava/util/List;Z\)V\n    \.locals \d+\n)'
    text, count = re.subn(pattern, lambda m: m[1] + '''
    invoke-interface {p2}, Ljava/util/List;->size()I
    move-result v0
    if-ltz p1, :offline_clipboard_first_tab
    if-lt p1, v0, :offline_clipboard_tab_ready
    :offline_clipboard_first_tab
    const/4 p1, 0x0
    :offline_clipboard_tab_ready
''', text)
    assert count == 1, 'Clipboard tab selection anchor changed'
    texts[cls] = text
    patches.append({'class': cls, 'method': 'setTabList', 'purpose': 'Clamp selection after removal of online tab'})

    cls = 'com/baidu/input/ime/logo/menu/LogoMenuView'
    text = source(cls)
    anchor = '    .line 190\n    invoke-virtual {v2, p2, p3}, Landroid/view/ViewGroup;->addView(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V'
    assert text.count(anchor) == 1, 'Menu header anchor changed'
    texts[cls] = text.replace(anchor, '    # Omit the account / membership menu header.\n    nop')
    patches.append({'class': cls, 'method': '<init>', 'purpose': 'Omit account and membership header'})

    cls = 'com/baidu/input/ime/logo/distribution/CandDistributeIconManager'
    for signature in ('n()V', 'o(Z)V', 'k(J)V', 'l(Z)V'):
        replace(cls, signature, '    .locals 0\n    return-void')

    cls = 'com/baidu/input/ime/editor/popupdelegate/logomenu/MenuClickProvider'
    text = source(cls)
    pattern = r'(?m)(^\.method public final Z3\(Lcom/baidu/input/menutoolapi/data/MenuFunction;Z\)V\n    \.locals \d+\n)'
    text, count = re.subn(pattern, lambda m: m[1] + '''
    invoke-static/range {p1 .. p1}, Llocal/baiduoffline/OfflineMenus;->allowed(Ljava/lang/Object;)Z
    move-result v0
    if-nez v0, :offline_menu_allowed
    return-void
    :offline_menu_allowed
''', text)
    assert count == 1
    texts[cls] = text
    patches.append({'class': cls, 'method': 'Z3', 'purpose': 'Accept only local menu actions'})

    # Local settings must not pass through the online shop homepage first.
    replace('com/baidu/input/pub/IntentManager',
            'startIntentThroughImeMain(BLjava/lang/String;IZLandroid/os/Bundle;)V', '''    .locals 1
    sget-object v0, Lcom/baidu/input/pub/ImeBaseGlobal;->m:Landroid/app/Application;
    invoke-static {v0, p0, p1, p4}, Lcom/baidu/input/pub/IntentManager;->startIntent(Landroid/content/Context;BLjava/lang/String;Landroid/os/Bundle;)Z
    return-void''')
