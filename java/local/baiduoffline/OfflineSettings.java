package local.baiduoffline;

import android.preference.Preference;
import android.preference.PreferenceActivity;
import android.preference.PreferenceGroup;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/** Retain the original preference bindings for local typing settings. */
public final class OfflineSettings {
    private static final Set<String> ROOT = new HashSet<>(Arrays.asList(
        "pref_key_general_setting", "pref_key_virtual", "pref_key_handwriting", "pref_key_LANGUAGE"));
    private static final String[] ONLINE = {
        "pref_key_YUNSHURU", "pref_key_smart_reply", "pref_key_intelligent_recommend",
        "pref_key_update_baibian_resources_in_wifi", "pref_key_logomenu_content_recommend",
        "pref_key_game_board_setting", "pref_key_game_board_alpha_setting",
        "pref_key_floatwindow", "pref_key_ciyu_switch"
    };

    private static String key(PreferenceActivity activity, String name) {
        int id = activity.getResources().getIdentifier(name, "string", activity.getPackageName());
        if (id == 0) throw new IllegalStateException("Settings resource missing: " + name);
        return activity.getString(id);
    }

    public static void filter(PreferenceActivity activity, int type) {
        if (activity == null || activity.getPreferenceScreen() == null) return;
        Set<String> allowed = null;
        Set<String> blocked = new HashSet<>();
        if (type == 0) {
            allowed = new HashSet<>();
            for (String name : ROOT) allowed.add(key(activity, name));
        }
        for (String name : ONLINE) blocked.add(key(activity, name));
        prune(activity.getPreferenceScreen(), allowed, blocked);
    }

    private static void prune(PreferenceGroup group, Set<String> allowed, Set<String> blocked) {
        for (int i = group.getPreferenceCount() - 1; i >= 0; i--) {
            Preference preference = group.getPreference(i);
            String key = preference.getKey();
            if ((allowed != null && !allowed.contains(key)) || blocked.contains(key)) {
                group.removePreference(preference);
            } else if (preference instanceof PreferenceGroup) {
                PreferenceGroup child = (PreferenceGroup) preference;
                prune(child, null, blocked);
                if (child.getPreferenceCount() == 0) group.removePreference(child);
            }
        }
    }
}
