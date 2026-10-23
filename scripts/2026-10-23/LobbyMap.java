// Read-only: map lobby/session/scanner classes (vftables -> constructors -> factory callers)
// and list instructions using displacement 0x3b0/0x3b4 (CLobby auth-type fields).
// Args: <outPath> <nameRegex> <dispHex,dispHex> <rangeStartHex> <rangeEndHex>
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;
import java.util.regex.Pattern;

public class LobbyMap extends GhidraScript {
    public void run() throws Exception {
        String[] a = getScriptArgs();
        PrintWriter out = new PrintWriter(new BufferedWriter(new FileWriter(a[0])));
        Pattern cls = Pattern.compile(String.join("|", a[1].split("\\+")));
        Set<Long> disps = new HashSet<>();
        for (String d : a[2].split("\\+")) disps.add(Long.parseLong(d, 16));
        Address lo = toAddr(a[3]), hi = toAddr(a[4]);
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();
        SymbolTable st = currentProgram.getSymbolTable();

        out.println("# VFTABLES");
        SymbolIterator it = st.getSymbols("vftable");
        while (it.hasNext()) {
            Symbol s = it.next();
            String ns = s.getParentNamespace().getName(true);
            if (!cls.matcher(ns).find()) continue;
            out.println("VFT " + s.getAddress() + " " + ns);
            for (int slot = 0; slot < 48; slot++) {
                Address p = s.getAddress().add(slot * 8L);
                if (slot > 0 && st.getPrimarySymbol(p) != null && st.getPrimarySymbol(p).getName().equals("vftable")) break;
                long v;
                try { v = currentProgram.getMemory().getLong(p); } catch (Exception e) { break; }
                Function f = fm.getFunctionAt(toAddr(v));
                if (f == null) break;
                out.println("  slot+0x" + Integer.toHexString(slot * 8) + " " + f.getEntryPoint() + " " + f.getName(true)
                        + " size=" + f.getBody().getNumAddresses());
            }
            Set<Function> ctors = new LinkedHashSet<>();
            for (Reference r : rm.getReferencesTo(s.getAddress())) {
                Function f = fm.getFunctionContaining(r.getFromAddress());
                if (f != null) ctors.add(f);
            }
            for (Function c : ctors) {
                StringBuilder callers = new StringBuilder();
                for (Reference r : rm.getReferencesTo(c.getEntryPoint())) {
                    Function cf = fm.getFunctionContaining(r.getFromAddress());
                    callers.append(cf != null ? cf.getEntryPoint().toString() : "data@" + r.getFromAddress()).append(' ');
                }
                out.println("  WRITER " + c.getEntryPoint() + " " + c.getName(true) + " <- " + callers);
            }
        }

        out.println("# DISPLACEMENT USES " + a[2] + " in [" + lo + "," + hi + "]");
        Listing listing = currentProgram.getListing();
        for (Instruction ins : listing.getInstructions(new AddressSet(lo, hi), true)) {
            for (int op = 0; op < ins.getNumOperands(); op++) {
                for (Object o : ins.getOpObjects(op)) {
                    if (o instanceof Scalar && disps.contains(((Scalar) o).getUnsignedValue())
                            && ins.toString().contains("[")) {
                        Function f = fm.getFunctionContaining(ins.getAddress());
                        out.println("DISP " + ins.getAddress() + " " + (f == null ? "?" : f.getEntryPoint() + " " + f.getName(true))
                                + " :: " + ins);
                    }
                }
            }
        }
        out.close();
        println("LobbyMap done -> " + a[0]);
    }
}
