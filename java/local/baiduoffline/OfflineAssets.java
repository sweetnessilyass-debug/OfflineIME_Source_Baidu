package local.baiduoffline;

import android.content.Context;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.security.MessageDigest;

public final class OfflineAssets {
    private static Context context;
    private static final long MODEL_SIZE = 78026351L;
    private static final String MODEL_HASH = "7e62989dc166e1ceab136e3268fa109f90a0817de9ff728906e3fa04342752e4";

    public static void attach(Context value) { context = value; OfflineNetwork.install(); }

    public static void recordCrash(String details) {
        try (FileOutputStream out = new FileOutputStream(new File(app().getFilesDir(), "offline-last-crash.txt"))) {
            out.write(String.valueOf(details).getBytes(java.nio.charset.StandardCharsets.UTF_8));
            out.getFD().sync();
        } catch (Exception ignored) { }
    }

    private static Context app() {
        if (context == null) throw new IllegalStateException("Application context unavailable");
        return context;
    }

    public static String modelPath() { return new File(app().getFilesDir(), "offline-voice/s_14").getPath(); }
    public static String libraryPath() {
        return new File(app().getApplicationInfo().nativeLibraryDir, "libbdTinyEasrAndroid_arm64_12.so").getPath();
    }
    public static boolean ready() {
        File model = new File(modelPath());
        return model.length() == MODEL_SIZE
            && new File(model.getParentFile(), MODEL_HASH + ".verified").isFile()
            && new File(libraryPath()).length() == 8647168L;
    }

    public static synchronized void prepare() throws Exception {
        if (ready()) return;
        File target = new File(modelPath());
        File directory = target.getParentFile();
        if (!directory.isDirectory() && !directory.mkdirs()) throw new Exception("Cannot create model directory");
        File partial = new File(directory, "s_14.partial");
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long length = 0;
        try (InputStream in = app().getAssets().open("offline-voice/s_14");
             FileOutputStream out = new FileOutputStream(partial)) {
            byte[] buffer = new byte[65536];
            int count;
            while ((count = in.read(buffer)) != -1) {
                out.write(buffer, 0, count); digest.update(buffer, 0, count); length += count;
            }
            out.getFD().sync();
        }
        StringBuilder hex = new StringBuilder();
        for (byte value : digest.digest()) hex.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
        if (length != MODEL_SIZE || !MODEL_HASH.equals(hex.toString())) {
            partial.delete(); throw new Exception("Model checksum mismatch");
        }
        if (target.exists() && !target.delete()) throw new Exception("Cannot replace incomplete model");
        if (!partial.renameTo(target)) throw new Exception("Cannot install model");
        new File(directory, MODEL_HASH + ".verified").createNewFile();
        if (!ready()) throw new Exception("Offline decoder library is unavailable");
    }

    public static void forceOffline(JSONObject params) {
        if (params == null) throw new IllegalArgumentException("Recognition parameters are required");
        try {
            if (!ready()) throw new IllegalStateException("Prepare the bundled model on the start page first");
            params.put("decoder", 1);
            params.put("basic.decoder", 1);
            params.put("asr-base-file-path", modelPath());
            params.put("decoder-offline.asr-base-file-path", modelPath());
            params.put("asr_library_custom_path", libraryPath());
            params.put("license-file-path", "assets:///license-android-easr-ime-1.dat");
            params.put("decoder-offline.license-file-path", "assets:///license-android-easr-ime-1.dat");
            params.put("accept-audio-data", false);
        } catch (Exception failure) { throw new IllegalStateException("Offline voice is not ready", failure); }
    }
}
