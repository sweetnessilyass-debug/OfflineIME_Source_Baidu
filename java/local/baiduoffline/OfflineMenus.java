package local.baiduoffline;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.ArrayList;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.content.res.Resources;

/** Local functions exposed through the original input method's icon handlers. */
public final class OfflineMenus {
    private static final String[] TOOLBAR = {"VOICE", "CLIPBOARD", "EDITOR", "IM"};
    private static final String[] PANEL = {
        "VOICE", "CLIPBOARD", "EDITOR", "IM", "ADJUSTHEIGHT", "NIGHTMODE",
        "SOUND", "VIBRATE", "SINGLE", "TRADITIONAL", "FLOAT_MODE", "SETTING", "HIDE_SOFTVIEW"
    };

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static ArrayList<Object> icons(String[] names, boolean rows) {
        try {
            Class<? extends Enum> function = (Class<? extends Enum>) Class.forName("com.baidu.input.menutoolapi.data.MenuFunction");
            Class<?> data = Class.forName("com.baidu.input.menutoolimpl.Data");
            Method current = data.getMethod("x", function);
            Method create = data.getMethod("w", function);
            Constructor<?> row = rows ? Class.forName("com.baidu.input.ime.logo.rv.model.MenuNormalLogoFunctionItemData")
                .getConstructor(Class.forName("com.baidu.input.menutoolapi.data.IMenuIcon")) : null;
            ArrayList<Object> result = new ArrayList<>();
            for (String name : names) {
                Object value = Enum.valueOf(function, "CLICK_INDEX_" + name);
                value = current.invoke(null, value);
                Object icon = create.invoke(null, value);
                if (rows) {
                    // The menu uses bitmap icons while the toolbar uses key codes.
                    // Prefer the bundled default icon rather than a skin-store icon.
                    Bitmap bitmap = (Bitmap) icon.getClass().getMethod("e").invoke(icon);
                    if (bitmap == null) {
                        bitmap = Bitmap.createBitmap(96, 96, Bitmap.Config.ARGB_8888);
                        Drawable fallback = Resources.getSystem().getDrawable(android.R.drawable.ic_menu_preferences, null);
                        fallback.setBounds(0, 0, 96, 96);
                        fallback.draw(new Canvas(bitmap));
                    }
                    icon.getClass().getField("d").set(icon, bitmap);
                    icon.getClass().getField("h").setBoolean(icon, true);
                }
                result.add(rows ? row.newInstance(icon) : icon);
            }
            return result;
        } catch (ReflectiveOperationException failure) {
            throw new IllegalStateException("Offline menu version mismatch", failure);
        }
    }

    public static ArrayList<Object> toolbar() { return icons(TOOLBAR, false); }
    public static ArrayList<Object> menu() { return icons(PANEL, false); }
    public static ArrayList<Object> rows() { return icons(PANEL, true); }

    public static ArrayList<Short> codes() {
        ArrayList<Short> result = new ArrayList<>();
        try {
            for (Object icon : toolbar()) result.add((Short) icon.getClass().getMethod("getCode").invoke(icon));
        } catch (ReflectiveOperationException failure) {
            throw new IllegalStateException("Offline toolbar version mismatch", failure);
        }
        return result;
    }

    public static boolean allowed(Object value) {
        if (!(value instanceof Enum<?>)) return false;
        String name = ((Enum<?>) value).name();
        for (String item : PANEL) if (name.equals("CLICK_INDEX_" + item)) return true;
        return name.equals("CLICK_INDEX_DAYMODE") || name.equals("CLICK_INDEX_DOUBLE")
            || name.equals("CLICK_INDEX_SIMPLIFIED") || name.equals("CLICK_INDEX_NOT_FLOAT_MODE")
            || name.equals("CLICK_INDEX_CLOSE_LOGOMENU");
    }
}
