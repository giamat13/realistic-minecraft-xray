package xray;

import java.io.PrintStream;
import java.lang.reflect.*;
import java.util.*;

/** Dumps every entity model layer of a Minecraft client jar as JSON (reflection only). */
public class Dump {
    static StringBuilder out = new StringBuilder();

    static void value(Object o, int depth) throws Exception {
        if (o == null) { out.append("null"); return; }
        if (o instanceof Number || o instanceof Boolean) { out.append(o); return; }
        if (o instanceof String || o instanceof Enum) { str(String.valueOf(o)); return; }
        if (depth > 40) { out.append("null"); return; }
        if (o.getClass().isArray()) {
            out.append('[');
            for (int i = 0; i < Array.getLength(o); i++) { if (i > 0) out.append(','); value(Array.get(o, i), depth + 1); }
            out.append(']'); return;
        }
        if (o instanceof Map<?, ?> m) {
            out.append('{'); boolean first = true;
            for (Map.Entry<?, ?> e : m.entrySet()) {
                if (!first) out.append(','); first = false;
                str(String.valueOf(e.getKey())); out.append(':'); value(e.getValue(), depth + 1);
            }
            out.append('}'); return;
        }
        if (o instanceof Collection<?> c) { value(c.toArray(), depth); return; }
        String n = o.getClass().getName();
        if (n.startsWith("org.joml.Vector3")) {
            out.append('[').append(o.getClass().getMethod("x").invoke(o)).append(',').append(o.getClass().getMethod("y").invoke(o))
               .append(',').append(o.getClass().getMethod("z").invoke(o)).append(']'); return;
        }
        out.append('{'); boolean first = true;
        for (Class<?> k = o.getClass(); k != null && k != Object.class && k != Record.class; k = k.getSuperclass()) {
            for (Field f : k.getDeclaredFields()) {
                if (Modifier.isStatic(f.getModifiers())) continue;
                f.setAccessible(true);
                if (!first) out.append(','); first = false;
                str(f.getName()); out.append(':'); value(f.get(o), depth + 1);
            }
        }
        out.append('}');
    }

    static void str(String s) {
        out.append('"');
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') out.append('\\').append(c);
            else if (c < 32) out.append(' ');
            else out.append(c);
        }
        out.append('"');
    }

    /** args: LayerDefinitions class, createRoots method, bakeRoot method, [SharedConstants, detect, Bootstrap, boot] */
    public static void main(String[] args) throws Exception {
        PrintStream real = System.out;
        System.setOut(System.err);
        if (args.length > 3) {
            try {
                call(args[3], args[4]);
                call(args[5], args[6]);
            } catch (Throwable t) { System.err.println("bootstrap failed: " + t); }
        }
        Map<?, ?> roots = (Map<?, ?>) call(args[0], args[1]);
        out.append('{'); boolean first = true;
        for (Map.Entry<?, ?> e : roots.entrySet()) {
            if (!first) out.append(','); first = false;
            str(String.valueOf(e.getKey())); out.append(":{\"def\":[");
            Object def = e.getValue();
            Method bake = def.getClass().getDeclaredMethod(args[2]);
            bake.setAccessible(true);
            // the texture size lives in the definition's material record, the geometry in the baked root
            boolean f1 = true;
            for (Field f : def.getClass().getDeclaredFields()) {
                if (Modifier.isStatic(f.getModifiers())) continue;
                f.setAccessible(true);
                Object v = f.get(def);
                if (hasInt(v)) { if (!f1) out.append(','); f1 = false; value(v, 0); }
            }
            out.append("],\"root\":"); value(bake.invoke(def), 0); out.append('}');
        }
        out.append('}');
        real.print(out);
        real.flush();
    }

    static boolean hasInt(Object v) {
        for (Field f : v.getClass().getDeclaredFields()) if (f.getType() == int.class && !Modifier.isStatic(f.getModifiers())) return true;
        return false;
    }

    static Object call(String cls, String method) throws Exception {
        Method m = Class.forName(cls).getDeclaredMethod(method);
        m.setAccessible(true);
        return m.invoke(null);
    }
}
