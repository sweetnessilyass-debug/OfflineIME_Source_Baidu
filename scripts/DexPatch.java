import java.io.File;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import com.android.tools.smali.dexlib2.DexFileFactory;
import com.android.tools.smali.dexlib2.Opcodes;
import com.android.tools.smali.dexlib2.iface.ClassDef;
import com.android.tools.smali.dexlib2.iface.DexFile;
import com.android.tools.smali.dexlib2.immutable.ImmutableDexFile;
import com.android.tools.smali.smali.Smali;
import com.android.tools.smali.smali.SmaliOptions;

/** Relocate patched classes to a small extra DEX; retain all other classes. */
public final class DexPatch {
    public static void main(String[] args) throws Exception {
        File source = new File(args[0]), output = new File(args[2]);
        output.mkdirs();
        SmaliOptions options = new SmaliOptions();
        options.apiLevel = 23;
        options.outputDexFile = new File(output, "patches.dex").toString();
        if (!Smali.assemble(options, args[1])) throw new IllegalStateException("Smali assembly failed");
        Opcodes opcodes = Opcodes.forApi(23);
        DexFile patch = DexFileFactory.loadDexFile(options.outputDexFile, opcodes);
        Map<String, ClassDef> replacements = new HashMap<>();
        for (ClassDef cls : patch.getClasses()) replacements.put(cls.getType(), cls);
        Set<String> applied = new HashSet<>();
        for (File file : source.listFiles()) {
            if (!file.getName().matches("classes[0-9]*\\.dex")) continue;
            DexFile original = DexFileFactory.loadDexFile(file, opcodes);
            ArrayList<ClassDef> classes = new ArrayList<>();
            int count = 0;
            for (ClassDef cls : original.getClasses()) {
                ClassDef replacement = replacements.get(cls.getType());
                if (replacement == null) classes.add(cls);
                else {
                    if (!applied.add(cls.getType())) throw new IllegalStateException("Duplicate original class");
                    count++;
                }
            }
            if (count > 0) {
                File dest = new File(output, file.getName());
                DexFileFactory.writeDexFile(dest.toString(), new ImmutableDexFile(opcodes, classes));
                if (DexFileFactory.loadDexFile(dest, opcodes).getClasses().size() != original.getClasses().size() - count)
                    throw new IllegalStateException("Class count changed");
                System.out.println(file.getName() + ": relocated " + count + " patched classes");
            }
        }
        if (!applied.equals(replacements.keySet())) throw new IllegalStateException("Unmatched patch classes");
    }
}
