// HKN Dentaire - uninstall flow, compiled into the launcher exe (HKN Dentaire.exe).
// Modes:
//   HKN Dentaire.exe /uninstall            -> interactive uninstall wizard
//   internal /selfdelete <authorization-id> -> final cleanup pass
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.IO.Pipes;
using System.Windows.Forms;
using Microsoft.Win32;
using Microsoft.Win32.SafeHandles;
using System.Runtime.InteropServices;

namespace HKN
{
    internal static class UninstallRunner
    {
        public static void Run()
        {
            string rootDir = Common.RootDir;
            if (!IsInstallationRoot(rootDir))
            {
                MessageBox.Show("Ce programme ne se trouve pas dans un dossier d'installation HKN Dentaire valide:\n" + rootDir, Common.AppName,
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            var res = MessageBox.Show(
                "Désinstaller HKN Dentaire ?\n\n" +
                "Le serveur local sera arrêté proprement. Vos données patients et\n" +
                "sauvegardes resteront par sécurité dans le dossier « data ».",
                "Désinstallation de " + Common.AppName, MessageBoxButtons.OKCancel, MessageBoxIcon.Question);
            if (res != DialogResult.OK) return;

            try
            {
                var psiSt = new ProcessStartInfo
                {
                    FileName = Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe",
                    Arguments = "/c \"\"" + Path.Combine(rootDir, "scripts", "stop.bat") + "\"\"",
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    WorkingDirectory = rootDir,
                };
                using (var p = Process.Start(psiSt)) p.WaitForExit(45000);
            }
            catch (Exception) { }
            KillAll(rootDir);
            if (HasPostgresUnder(rootDir))
            {
                MessageBox.Show(
                    "La base PostgreSQL est encore en cours d'ex\u00e9cution. Aucun fichier n'a \u00e9t\u00e9 supprim\u00e9.\n\nFermez HKN Dentaire et relancez la d\u00e9sinstallation.",
                    Common.AppName, MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            var purgeRes = MessageBox.Show(
                "Effacer aussi les données (patients, sauvegardes) ?\n\n" +
                "Oui = tout effacer\nNon = conserver le dossier « data » (recommandé)",
                Common.AppName, MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2);
            if (purgeRes == DialogResult.Yes)
            {
                // Second, explicit confirmation: PURGE is irreversible and also
                // removes the backups, which are usually the only other copy.
                var confirmRes = MessageBox.Show(
                    "ATTENTION : suppression définitive.\n\n" +
                    "Seront effacés sans possibilité de récupération :\n" +
                    "  • la base de données des patients (data\\pgdata)\n" +
                    "  • TOUTES les sauvegardes (" + Path.Combine(rootDir, "data", "backups") + ")\n" +
                    "  • les pièces jointes et la licence (dossier « data »)\n\n" +
                    "Si vous n'avez pas copié une sauvegarde ailleurs (clé USB…), répondez Non.\n\n" +
                    "Oui = tout effacer définitivement\nNon = conserver le dossier « data »",
                    Common.AppName, MessageBoxButtons.YesNo, MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2);
                if (confirmRes != DialogResult.Yes) purgeRes = DialogResult.No;
            }

            // LAN firewall rule of THIS install (asks for elevation only if it exists)
            string fwError = Firewall.RemoveFor(rootDir);
            if (fwError != null)
                MessageBox.Show("La règle de pare-feu « " + Firewall.RuleName + " » n'a pas pu être supprimée :\n" + fwError +
                    "\n\nVous pourrez la supprimer dans « Pare-feu Windows Defender > Paramètres avancés ».",
                    Common.AppName, MessageBoxButtons.OK, MessageBoxIcon.Information);

            // Start-with-Windows (HKCU Run): removed only if it starts THIS install.
            Common.RemoveAutostartFor(rootDir);

            // Shortcuts are shared, so only remove them when this path is the
            // installation currently registered to Windows.
            if (SelfDelete.IsRegisteredInstall(rootDir))
            {
                try
                {
                    string desk = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "HKN Dentaire.lnk");
                    if (File.Exists(desk)) File.Delete(desk);
                }
                catch (Exception) { }
                try
                {
                    string sm = Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                        "Microsoft", "Windows", "Start Menu", "Programs", "HKN Dentaire.lnk");
                    if (File.Exists(sm)) File.Delete(sm);
                }
                catch (Exception) { }
            }
            bool purge = purgeRes == DialogResult.Yes;

            // Spawn the cleanup pass from a copy in %TEMP% so it can delete the
            // installed executable. The one-time authorization binds the helper
            // to this install and to the mode the user just confirmed.
            try
            {
                string authorizationId = Guid.NewGuid().ToString("N");
                string pipeName = "HKN.Uninstall." + authorizationId;
                string selfCopy = Path.Combine(Path.GetTempPath(), "HKN_uninstall_" + authorizationId + ".exe");
                File.Copy(System.Reflection.Assembly.GetExecutingAssembly().Location, selfCopy, true);
                using (var pipe = new NamedPipeServerStream(pipeName, PipeDirection.Out, 1,
                    PipeTransmissionMode.Byte, PipeOptions.Asynchronous)) // required by BeginWaitForConnection
                {
                    string mode = purge ? "PURGE" : "KEEPDATA";
                    var psi = new ProcessStartInfo
                    {
                        FileName = selfCopy,
                        Arguments = "/selfdelete " + mode + " " + Process.GetCurrentProcess().Id + " " + pipeName,
                        CreateNoWindow = true,
                        UseShellExecute = false,
                    };
                    using (Process.Start(psi))
                    {
                        IAsyncResult connect = pipe.BeginWaitForConnection(null, null);
                        if (!connect.AsyncWaitHandle.WaitOne(15000))
                            throw new TimeoutException("Le processus de nettoyage n'a pas répondu.");
                        pipe.EndWaitForConnection(connect);
                        byte[] confirmation = System.Text.Encoding.ASCII.GetBytes("HKN-UNINSTALL-CONFIRMED:" + mode);
                        pipe.Write(confirmation, 0, confirmation.Length);
                        pipe.Flush();
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("Nettoyage: " + ex.Message, Common.AppName,
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }

        public static void KillAll(string rootDir)
        {
            bool changed = true;
            while (changed)
            {
                changed = false;
                try
                {
                    foreach (var proc in Process.GetProcessesByName("python"))
                    {
                        try
                        {
                            if (proc.HasExited) continue;
                            if (IsHknPython(proc, rootDir))
                            {
                                proc.Kill();
                                changed = true;
                            }
                        }
                        finally { proc.Dispose(); }
                    }
                    foreach (var proc in Process.GetProcessesByName("HKN Dentaire"))
                    {
                        try
                        {
                            if (proc.Id == Process.GetCurrentProcess().Id) continue;
                            string cl = Common.CommandLineOf(proc.Id);
                            if (cl != null && CommandLineContainsRoot(cl, rootDir))
                            {
                                proc.Kill();
                                changed = true;
                            }
                        }
                        finally { proc.Dispose(); }
                    }
                }
                catch (Exception) { }
            }
        }

        public static bool HasPostgresUnder(string rootDir)
        {
            try
            {
                string fullRoot = Path.GetFullPath(rootDir).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                foreach (var proc in Process.GetProcessesByName("postgres"))
                {
                    try
                    {
                        if (proc.HasExited) continue;
                        string cl = Common.CommandLineOf(proc.Id);
                        if (cl != null && CommandLineContainsRoot(cl, fullRoot)) return true;
                        try
                        {
                            string image = Path.GetFullPath(proc.MainModule.FileName);
                            if (image.StartsWith(fullRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) return true;
                        }
                        catch (Exception)
                        {
                            // If Windows will not reveal either command line or image,
                            // fail closed instead of risking removal of a live database.
                            if (cl == null) return true;
                        }
                    }
                    finally { proc.Dispose(); }
                }
            }
            catch (Exception) { return true; }
            return false;
        }

        // Only the bundled interpreter (root\runtime\python.exe) or a python
        // running HKN's own backend counts. A bare "root appears somewhere in
        // the command line" match would also kill the user's unrelated python
        // scripts when root is a shared folder such as Documents.
        static bool IsHknPython(Process proc, string rootDir)
        {
            string root;
            try { root = Path.GetFullPath(rootDir).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar); }
            catch (Exception) { return false; }
            try
            {
                string image = Path.GetFullPath(proc.MainModule.FileName);
                if (image.StartsWith(Path.Combine(root, "runtime") + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                    return true;
            }
            catch (Exception) { }
            string cl = Common.CommandLineOf(proc.Id);
            if (cl == null) return false;
            return CommandLineContainsRoot(cl, Path.Combine(root, "runtime")) ||
                   CommandLineContainsRoot(cl, Path.Combine(root, "backend"));
        }

        static bool CommandLineContainsRoot(string commandLine, string rootDir)
        {
            try
            {
                string root = Path.GetFullPath(rootDir).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                string command = commandLine.Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);
                int start = 0;
                while ((start = command.IndexOf(root, start, StringComparison.OrdinalIgnoreCase)) >= 0)
                {
                    int end = start + root.Length;
                    if (end == command.Length || command[end] == Path.DirectorySeparatorChar || command[end] == '"') return true;
                    start = end;
                }
            }
            catch (Exception) { }
            return false;
        }

        internal static bool IsInstallationRoot(string root)
        {
            try
            {
                string full = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                string pathRoot = Path.GetPathRoot(full);
                if (string.IsNullOrEmpty(full) || string.Equals(full, pathRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
                    StringComparison.OrdinalIgnoreCase)) return false;
                return Directory.Exists(Path.Combine(full, "data")) &&
                    File.Exists(Path.Combine(full, "scripts", "HKN Dentaire.exe")) &&
                    File.Exists(Path.Combine(full, "scripts", "stop.bat")) &&
                    File.Exists(Path.Combine(full, "backend", "app", "cli.py")) &&
                    File.Exists(Path.Combine(full, "runtime", "python.exe"));
            }
            catch (Exception) { return false; }
        }
    }

    // Windows Firewall program rule for LAN access: allows inbound connections
    // to THIS install's runtime\python.exe on private + domain networks only.
    internal static class Firewall
    {
        public const string RuleName = "HKN Dentaire LAN";

        static string PythonOf(string root)
        {
            return Path.Combine(Path.GetFullPath(root).TrimEnd('\\'), "runtime", "python.exe");
        }

        // null = success, otherwise a French reason.
        public static string Add(string root)
        {
            string prog = PythonOf(root);
            string args = "/c netsh advfirewall firewall delete rule name=\"" + RuleName + "\" program=\"" + prog + "\" >nul 2>&1" +
                          " & netsh advfirewall firewall delete rule name=\"" + RuleName + "\" protocol=tcp localport=8000 >nul 2>&1" +
                          " & netsh advfirewall firewall add rule name=\"" + RuleName + "\" dir=in action=allow enable=yes" +
                          " program=\"" + prog + "\" profile=private,domain";
            return RunElevated(args);
        }

        // Removes the rule only when one exists for this install's python.exe.
        // Returns null when there was nothing to do or removal succeeded.
        public static string RemoveFor(string root)
        {
            string prog = PythonOf(root);
            try
            {
                var psi = new ProcessStartInfo("netsh", "advfirewall firewall show rule name=\"" + RuleName + "\" verbose")
                {
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                };
                string outp;
                using (var p = Process.Start(psi))
                {
                    outp = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(15000);
                }
                if (outp.IndexOf(prog, StringComparison.OrdinalIgnoreCase) < 0) return null;
            }
            catch (Exception) { return null; }
            return RunElevated("/c netsh advfirewall firewall delete rule name=\"" + RuleName + "\" program=\"" + prog + "\"");
        }

        static string RunElevated(string cmdArgs)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe",
                    Arguments = cmdArgs,
                    Verb = "runas",
                    UseShellExecute = true,
                    WindowStyle = ProcessWindowStyle.Hidden,
                };
                using (var p = Process.Start(psi))
                {
                    if (p == null) return "netsh n'a pas démarré";
                    if (!p.WaitForExit(60000)) return "netsh ne répond pas";
                    return p.ExitCode == 0 ? null : "netsh a échoué (code " + p.ExitCode + ")";
                }
            }
            catch (System.ComponentModel.Win32Exception ex)
            {
                return ex.NativeErrorCode == 1223 ? "autorisation administrateur refusée" : ex.Message;
            }
            catch (Exception ex) { return ex.Message; }
        }
    }

    internal static class SelfDelete
    {
        public static void Run(string[] args)
        {
            // Accept cleanup only through a live pipe owned by the uninstalling
            // launcher process. The target is derived from that process image,
            // so a second install cannot redirect cleanup through the registry.
            if (args == null || args.Length != 4 ||
                !string.Equals(args[0], "/selfdelete", StringComparison.OrdinalIgnoreCase)) return;
            bool purge = string.Equals(args[1], "PURGE", StringComparison.OrdinalIgnoreCase);
            if (!purge && !string.Equals(args[1], "KEEPDATA", StringComparison.OrdinalIgnoreCase)) return;
            int parentPid;
            if (!int.TryParse(args[2], out parentPid) || parentPid <= 0) return;
            const string pipePrefix = "HKN.Uninstall.";
            Guid pipeId;
            if (!args[3].StartsWith(pipePrefix, StringComparison.Ordinal) ||
                !Guid.TryParseExact(args[3].Substring(pipePrefix.Length), "N", out pipeId)) return;
            string parentImage;
            try { parentImage = Process.GetProcessById(parentPid).MainModule.FileName; }
            catch (Exception) { return; }
            if (!string.Equals(Path.GetFileName(parentImage), "HKN Dentaire.exe", StringComparison.OrdinalIgnoreCase)) return;
            string scriptsDir = Path.GetDirectoryName(Path.GetFullPath(parentImage));
            if (!string.Equals(Path.GetFileName(scriptsDir), "scripts", StringComparison.OrdinalIgnoreCase)) return;
            DirectoryInfo parentDir = Directory.GetParent(scriptsDir);
            if (parentDir == null) return;
            string root = parentDir.FullName;
            string expectedConfirmation = "HKN-UNINSTALL-CONFIRMED:" + args[1];
            try
            {
                using (var pipe = new NamedPipeClientStream(".", args[3], PipeDirection.In, PipeOptions.None))
                {
                    pipe.Connect(15000);
                    uint serverPid;
                    if (!NativeMethods.GetNamedPipeServerProcessId(pipe.SafePipeHandle, out serverPid) || serverPid != (uint)parentPid) return;
                    byte[] confirmation = new byte[expectedConfirmation.Length];
                    int received = 0;
                    while (received < confirmation.Length)
                    {
                        int count = pipe.Read(confirmation, received, confirmation.Length - received);
                        if (count <= 0) return;
                        received += count;
                    }
                    if (!string.Equals(System.Text.Encoding.ASCII.GetString(confirmation), expectedConfirmation, StringComparison.Ordinal)) return;
                }
            }
            catch (Exception) { return; }
            if (string.IsNullOrEmpty(root) || !UninstallRunner.IsInstallationRoot(root)) return;
            if (!File.Exists(Path.Combine(scriptsDir, "HKN Dentaire.exe")) ||
                string.Equals(root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
                    Path.GetPathRoot(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
                    StringComparison.OrdinalIgnoreCase)) return;
            Thread.Sleep(1800); // let the parent process exit so its exe is not locked

            try { RemoveInstalledFiles(root, purge); }
            catch (Exception) { }
            // The %TEMP% helper copy is running, so this usually fails; harmless.
            try { File.Delete(System.Reflection.Assembly.GetExecutingAssembly().Location); }
            catch (Exception) { }
            RemoveUninstallRegistration(root);
        }

        const string ManifestName = "MANIFEST.txt";

        // Application directories owned entirely by HKN Dentaire. Their whole
        // content (including runtime-generated __pycache__, logs...) is removed.
        static readonly string[] KnownAppDirs = { "backend", Path.Combine("frontend", ".output"), "runtime", "scripts",
                                                   "_upgrade_staging", "_upgrade_old" };

        // Delete ONLY what HKN Dentaire installed: files listed in MANIFEST.txt
        // and the known application directories. Unknown files that share the
        // install folder (e.g. a legacy install made directly in Documents) are
        // never deleted, and no directory is ever recurse-deleted except the
        // known application directories (and data\ in PURGE mode).
        static void RemoveInstalledFiles(string root, bool purge)
        {
            root = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string dataPath = Path.Combine(root, "data");
            var dirsToPrune = new System.Collections.Generic.HashSet<string>(StringComparer.OrdinalIgnoreCase);

            // 1) manifest-listed files (missing manifest => known dirs only)
            string manifest = Path.Combine(root, ManifestName);
            foreach (string rel in ReadManifest(manifest))
            {
                string full;
                try { full = Path.GetFullPath(Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar))); }
                catch (Exception) { continue; }
                if (!IsUnder(full, root) || string.Equals(full, root, StringComparison.OrdinalIgnoreCase)) continue;
                if (IsUnder(full, dataPath)) continue;
                try { if (File.Exists(full)) File.Delete(full); }
                catch (Exception) { }
                for (string d = Path.GetDirectoryName(full);
                     d != null && IsUnder(d, root) && !string.Equals(d, root, StringComparison.OrdinalIgnoreCase);
                     d = Path.GetDirectoryName(d))
                    dirsToPrune.Add(d);
            }

            // 2) known application directories
            bool dedicatedFolder = string.Equals(Path.GetFileName(root), "HKN Dentaire", StringComparison.OrdinalIgnoreCase);
            var known = KnownAppDirs.ToList();
            // "app" is only ours when the root is a dedicated HKN Dentaire folder.
            if (dedicatedFolder) known.Add("app");
            foreach (string sub in known)
            {
                string dir = Path.Combine(root, sub);
                try { if (Directory.Exists(dir)) Directory.Delete(dir, true); }
                catch (Exception) { DeleteFilesBestEffort(dir); }
                for (string d = Path.GetDirectoryName(dir);
                     d != null && IsUnder(d, root) && !string.Equals(d, root, StringComparison.OrdinalIgnoreCase);
                     d = Path.GetDirectoryName(d))
                    dirsToPrune.Add(d);
            }

            // 3) the manifest itself, last, so an interrupted run can be resumed
            try { if (File.Exists(manifest)) File.Delete(manifest); }
            catch (Exception) { }

            // 4) PURGE: data\ was explicitly (twice) confirmed by the user
            if (purge)
            {
                try { if (Directory.Exists(dataPath)) Directory.Delete(dataPath, true); }
                catch (Exception) { DeleteFilesBestEffort(dataPath); }
            }

            // 5) remove directories that are now empty (never recursive), deepest first
            foreach (string d in dirsToPrune.OrderByDescending(x => x.Length))
            {
                try { if (Directory.Exists(d) && !Directory.EnumerateFileSystemEntries(d).Any()) Directory.Delete(d, false); }
                catch (Exception) { }
            }
            try { if (Directory.Exists(root) && !Directory.EnumerateFileSystemEntries(root).Any()) Directory.Delete(root, false); }
            catch (Exception) { }
        }

        static System.Collections.Generic.List<string> ReadManifest(string path)
        {
            var rels = new System.Collections.Generic.List<string>();
            try
            {
                if (!File.Exists(path)) return rels;
                foreach (string raw in File.ReadAllLines(path, System.Text.Encoding.UTF8))
                {
                    // "<64 hex sha256>  <relative/posix/path>"
                    string line = raw.TrimEnd('\r');
                    if (line.Length < 67 || line[64] != ' ' || line[65] != ' ') continue;
                    bool hex = true;
                    for (int i = 0; i < 64 && hex; i++) hex = Uri.IsHexDigit(line[i]);
                    if (!hex) continue;
                    string rel = line.Substring(66).Trim();
                    if (rel.Length == 0 || Path.IsPathRooted(rel) || rel.IndexOf(':') >= 0 ||
                        rel.Split('/', '\\').Any(s => s == "..")) continue;
                    rels.Add(rel);
                }
            }
            catch (Exception) { }
            return rels;
        }

        static void DeleteFilesBestEffort(string dir)
        {
            try
            {
                if (!Directory.Exists(dir)) return;
                foreach (var f in Directory.EnumerateFiles(dir, "*", SearchOption.AllDirectories).ToList())
                {
                    try { File.SetAttributes(f, FileAttributes.Normal); File.Delete(f); }
                    catch (Exception) { }
                }
                foreach (var d in Directory.EnumerateDirectories(dir, "*", SearchOption.AllDirectories)
                         .OrderByDescending(x => x.Length).ToList())
                {
                    try { Directory.Delete(d, false); }
                    catch (Exception) { }
                }
                Directory.Delete(dir, false);
            }
            catch (Exception) { }
        }

        static void RemoveUninstallRegistration(string root)
        {
            try
            {
                using (var key = Registry.CurrentUser.OpenSubKey(
                    @"Software\Microsoft\Windows\CurrentVersion\Uninstall\HKN Dentaire", true))
                {
                    if (key == null) return;
                    string registered = key.GetValue("InstallLocation") as string;
                    if (string.IsNullOrWhiteSpace(registered)) return;
                    string full = Path.GetFullPath(registered.Trim()).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                    if (string.Equals(full, root, StringComparison.OrdinalIgnoreCase))
                        Registry.CurrentUser.DeleteSubKey(
                            @"Software\Microsoft\Windows\CurrentVersion\Uninstall\HKN Dentaire", false);
                }
            }
            catch (Exception) { }
        }

        internal static bool IsRegisteredInstall(string root)
        {
            try
            {
                using (var key = Registry.CurrentUser.OpenSubKey(
                    @"Software\Microsoft\Windows\CurrentVersion\Uninstall\HKN Dentaire", false))
                {
                    string registered = key == null ? null : key.GetValue("InstallLocation") as string;
                    if (string.IsNullOrWhiteSpace(registered)) return false;
                    string full = Path.GetFullPath(registered.Trim()).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                    return string.Equals(full, root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
                        StringComparison.OrdinalIgnoreCase);
                }
            }
            catch (Exception) { return false; }
        }

        static bool IsUnder(string path, string baseDir)
        {
            if (string.Equals(path, baseDir, StringComparison.OrdinalIgnoreCase)) return true;
            return path.StartsWith(baseDir + System.IO.Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
        }

        static class NativeMethods
        {
            [DllImport("kernel32.dll", SetLastError = true)]
            internal static extern bool GetNamedPipeServerProcessId(SafePipeHandle pipe, out uint serverProcessId);
        }
    }
}
