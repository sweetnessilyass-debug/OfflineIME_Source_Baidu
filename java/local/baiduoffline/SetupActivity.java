package local.baiduoffline;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.provider.Settings;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.lang.reflect.Proxy;
import org.json.JSONArray;
import org.json.JSONObject;

/** Local test screen. Audio is handled by the bundled SDK; no network permission. */
public final class SetupActivity extends Activity {
    private TextView status;
    private EditText editor;
    private Object listener;
    private Class<?> speech;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        OfflineAssets.attach(getApplication());
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int pad = (int)(20 * getResources().getDisplayMetrics().density);
        layout.setPadding(pad, pad, pad, pad);
        TextView title = new TextView(this); title.setTextSize(23);
        title.setText("百度离线输入\n0.2 · 内置离线语音"); layout.addView(title);
        TextView intro = new TextView(this);
        intro.setText("打字和普通话语音均在本地完成。点击键盘左上角菜单，可调整布局、音效、振动等本地设置。");
        layout.addView(intro);
        status = new TextView(this); status.setTextIsSelectable(true); layout.addView(status);
        button(layout, "1. 准备 / 检查内置语音资源", () -> prepare());
        button(layout, "2. 启用输入法", () -> startActivity(new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS)));
        button(layout, "3. 切换输入法", () -> ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showInputMethodPicker());
        button(layout, "4. 允许麦克风", () -> requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1));
        button(layout, "输入与键盘设置（模糊音 / 操作习惯）", () -> startActivity(
            new Intent().setClassName(this, "com.baidu.input.ImeMainConfigActivity")));
        editor = new EditText(this); editor.setHint("试打区：可用九宫格或键盘麦克风输入");
        editor.setMinLines(3); editor.setSingleLine(false); layout.addView(editor);
        if ((getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            button(layout, "直接测试离线语音", () -> startVoice());
            button(layout, "结束录音", () -> stopVoice());
        }
        ScrollView scroll = new ScrollView(this); scroll.addView(layout); setContentView(scroll);
        prepare();
    }

    private void button(LinearLayout layout, String text, Runnable action) {
        Button button = new Button(this); button.setText(text);
        button.setOnClickListener(view -> { try { action.run(); } catch (Throwable e) { showFailure(e); } });
        layout.addView(button);
    }

    private void prepare() {
        status.setText("正在校验并准备内置资源……");
        new Thread(() -> {
            try { OfflineAssets.prepare(); runOnUiThread(() -> status.setText("离线模型与解码库已准备好；可授权麦克风后测试。")); }
            catch (Throwable e) { runOnUiThread(() -> showFailure(e)); }
        }, "OfflineModelInstall").start();
    }

    private void startVoice() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1); return;
        }
        try {
            if (!OfflineAssets.ready()) { prepare(); return; }
            speech = Class.forName("com.baidu.speech.SpeechEventManager");
            Class<?> callback = Class.forName("com.baidu.speech.IEventListener");
            if (listener == null) listener = Proxy.newProxyInstance(callback.getClassLoader(), new Class<?>[]{callback}, (proxy, method, args) -> {
                if (method.getDeclaringClass() == Object.class) {
                    if (method.getName().equals("hashCode")) return System.identityHashCode(proxy);
                    if (method.getName().equals("equals")) return proxy == args[0];
                    return "OfflineVoiceListener";
                }
                if (args != null && args.length >= 2) {
                    final String name = String.valueOf(args[0]), data = String.valueOf(args[1]);
                    runOnUiThread(() -> handleEvent(name, data));
                }
                return null;
            });
            JSONObject params = new JSONObject();
            OfflineAssets.forceOffline(params);
            status.setText("正在离线录音，请说一句普通话，完成后点击结束录音。");
            speech.getMethod("startMic", android.content.Context.class, JSONObject.class, callback).invoke(null, this, new JSONObject(params.toString()), listener);
            speech.getMethod("startAsr", android.content.Context.class, JSONObject.class, callback).invoke(null, this, params, listener);
        } catch (Throwable e) { showFailure(e); }
    }

    private void handleEvent(String name, String data) {
        if (isFinishing()) return;
        if (name.contains("volume") || name.contains("audio")) return;
        status.setText(name + "\n" + data);
        if (name.equals("asr.partial")) {
            try {
                JSONObject result = new JSONObject(data);
                JSONArray values = result.optJSONArray("results_recognition");
                if ("final_result".equals(result.optString("result_type")) && values != null && values.length() > 0)
                    editor.append(values.getString(0));
            } catch (Exception ignored) { }
        }
    }

    private void stopVoice() {
        try { if (speech != null) {
            speech.getMethod("stopASR").invoke(null);
            speech.getMethod("closeMic").invoke(null);
        } }
        catch (Throwable e) { showFailure(e); }
    }

    private void showFailure(Throwable failure) {
        while (failure.getCause() != null) failure = failure.getCause();
        status.setText("操作未完成：" + failure.getMessage());
    }

    @Override public void onPause() { stopVoice(); super.onPause(); }
    @Override public void onDestroy() {
        try { if (speech != null) speech.getMethod("exitASR").invoke(null); } catch (Throwable ignored) { }
        super.onDestroy();
    }
}
