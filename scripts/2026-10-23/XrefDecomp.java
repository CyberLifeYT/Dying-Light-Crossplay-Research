// Read-only: for each address, dump function identity, callers (incl. vtable data refs),
// callees, referenced strings, and decompiled C.
// Args: <outPath> <hexAddr> [<hexAddr> ...]
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.StringDataInstance;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class XrefDecomp extends GhidraScript {
    private String nearestSymbol(Address a) {
        SymbolTable st = currentProgram.getSymbolTable();
        Address cur = a;
        if (!a.isMemoryAddress()) return a.toString();
        for (int i = 0; i < 0x400 && cur != null; i += 8) {
            Symbol s = st.getPrimarySymbol(cur);
            if (s != null && !s.getName().startsWith("PTR_") && !s.getName().startsWith("DAT_")) {
                long off = a.subtract(cur);
                return s.getName(true) + (off != 0 ? "+0x" + Long.toHexString(off) : "");
            }
            if (cur.getOffset() < 8) break;
            cur = cur.subtract(8);
        }
        return "?";
    }

    public void run() throws Exception {
        String[] args = getScriptArgs();
        PrintWriter out = new PrintWriter(new BufferedWriter(new FileWriter(args[0])));
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();
        Listing listing = currentProgram.getListing();
        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        ifc.setOptions(new DecompileOptions());
        out.println("# program=" + currentProgram.getName() + " md5=" + currentProgram.getExecutableMD5()
                + " sha256=" + currentProgram.getExecutableSHA256());
        for (int k = 1; k < args.length; k++) {
            Address a = toAddr(args[k]);
            Function f = fm.getFunctionAt(a);
            if (f == null) f = fm.getFunctionContaining(a);
            if (f == null) { out.println("//==== NO_FUNCTION " + args[k]); continue; }
            out.println("//==== FUNC " + f.getEntryPoint() + " " + f.getName(true) + " size="
                    + f.getBody().getNumAddresses() + " thunk=" + f.isThunk());
            for (Reference r : rm.getReferencesTo(f.getEntryPoint())) {
                Address from = r.getFromAddress();
                Function cf = fm.getFunctionContaining(from);
                String who = cf != null ? cf.getName(true) + "@" + cf.getEntryPoint() : "DATA " + nearestSymbol(from);
                out.println("//CALLER " + from + " " + r.getReferenceType() + " " + who);
            }
            for (Function c : f.getCalledFunctions(monitor)) {
                out.println("//CALLEE " + c.getEntryPoint() + " " + c.getName(true) + (c.isExternal() ? " EXTERNAL" : ""));
            }
            Set<String> strs = new LinkedHashSet<>();
            for (Instruction ins : listing.getInstructions(f.getBody(), true)) {
                for (Reference r : ins.getReferencesFrom()) {
                    Data d = listing.getDataAt(r.getToAddress());
                    if (d != null && d.hasStringValue()) {
                        strs.add(r.getToAddress() + " " + StringDataInstance.getStringDataInstance(d).getStringValue());
                    }
                }
            }
            for (String s : strs) out.println("//STRING " + s);
            DecompileResults res = ifc.decompileFunction(f, 120, monitor);
            if (res != null && res.decompileCompleted()) out.println(res.getDecompiledFunction().getC());
            else out.println("//DECOMPILE_FAILED " + (res == null ? "null" : res.getErrorMessage()));
            out.println();
        }
        out.close();
        ifc.dispose();
        println("XrefDecomp done -> " + args[0]);
    }
}
