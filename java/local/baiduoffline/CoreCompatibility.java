package local.baiduoffline;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.Signature;
import android.os.Parcel;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;

/** Compatibility metadata passed only to the unmodified native input core. */
public final class CoreCompatibility {
    public static PackageInfo forCore(Context context, PackageInfo original) {
        if (original == null) throw new IllegalArgumentException("Package metadata is unavailable");
        Parcel parcel = Parcel.obtain();
        try (InputStream in = context.getAssets().open("offline-voice/core-original-public-certificate.der")) {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            int count;
            while ((count = in.read(buffer)) != -1) bytes.write(buffer, 0, count);
            original.writeToParcel(parcel, 0);
            parcel.setDataPosition(0);
            PackageInfo copy = PackageInfo.CREATOR.createFromParcel(parcel);
            copy.signatures = new Signature[]{new Signature(bytes.toByteArray())};
            return copy;
        } catch (Exception failure) {
            throw new IllegalStateException("Input core compatibility metadata unavailable", failure);
        } finally { parcel.recycle(); }
    }
}
