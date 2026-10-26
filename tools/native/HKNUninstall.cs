// HKN Dentaire - uninstall flow, compiled into the launcher exe (HKN Dentaire.exe).
// Modes:
//   HKN Dentaire.exe /uninstall            -> interactive uninstall wizard
//   HKN Dentaire.exe /selfdelete <root> [KEEPDATA|PURGE]  -> final cleanup pass
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

namespace HKN
{
    internal static class UninstallRunner
    {
        public static void Run()
        {
            string rootDir = Common.RootDir;
            if (!Directory.Exists(rootDir))
            {
                MessageBox.Show("Dossier introuvable:\n" + rootDir, Common.AppName,
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

            var purgeRes = MessageBox.Show(
                "Effacer aussi les données (patients, sauvegardes) ?\n\n" +
                "Oui = tout effacer\nNon = conserver le dossier « data » (recommandé)",
                Common.AppName, MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2);

            // registry + shortcuts
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
            try
            {
                Registry.CurrentUser.DeleteSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\HKN Dentaire", false);
            }
            catch (Exception) { }

            bool purge = purgeRes == DialogResult.Yes;

            // spawn the cleanup pass from a copy in %TEMP% so we can delete our own exe
            try
            {
                string selfCopy = Path.Combine(Path.GetTempPath(), "HKN_uninstall_tmp.exe");
                File.Copy(System.Reflection.Assembly.GetExecutingAssembly().Location, selfCopy, true);
                var psi = new ProcessStartInfo
                {
                    FileName = selfCopy,
                    Arguments = "/selfdelete \"" + rootDir + "\" " + (purge ? "PURGE" : "KEEPDATA"),
                    CreateNoWindow = true,
                    UseShellExecute = false,
                };
                Process.Start(psi);
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
                            string cl = Common.CommandLineOf(proc.Id);
                            if (cl != null && cl.IndexOf(rootDir, StringComparison.OrdinalIgnoreCase) >= 0)
                            {
                                proc.Kill();
                                changed = true;
                            }
                        }
                        finally { proc.Dispose(); }
                    }
                    foreach (var proc in Process.GetProcessesByName("postgres"))
                    {
                        try
                        {
                            if (proc.HasExited) continue;
                            string cl = Common.CommandLineOf(proc.Id);
                            if (cl != null && cl.IndexOf(rootDir, StringComparison.OrdinalIgnoreCase) >= 0)
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
                            if (cl != null && cl.IndexOf(rootDir, StringComparison.OrdinalIgnoreCase) >= 0)
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
    }

    internal static class SelfDelete
    {
        public static void Run(string[] args)
        {
            // args: /selfdelete <root> [KEEPDATA|PURGE]
            if (args == null || args.Length < 3) return;
            string root = args[1];
            bool purge = string.Equals(args[2], "PURGE", StringComparison.OrdinalIgnoreCase);
            Thread.Sleep(1800); // let the parent process exit so its exe is not locked

            try
            {
                string dataPath = Path.Combine(root, "data");
                foreach (var f in Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories).ToList())
                {
                    if (IsUnder(f, dataPath)) continue;
                    try { File.Delete(f); }
                    catch (Exception) { }
                }
                if (purge)
                {
                    foreach (var d in Directory.EnumerateDirectories(root, "*", SearchOption.AllDirectories)
                             .OrderByDescending(d => d.Length).ToList())
                    {
                        try { Directory.Delete(d, true); }
                        catch (Exception) { }
                    }
                    try { File.Delete(System.Reflection.Assembly.GetExecutingAssembly().Location); }
                    catch (Exception) { }
                    try { Directory.Delete(root, true); }
                    catch (Exception) { }
                }
                else
                {
                    // remove empty application directories, keep only data\*
                    foreach (var d in Directory.EnumerateDirectories(root, "*", SearchOption.AllDirectories)
                             .OrderByDescending(d => d.Length).ToList())
                    {
                        if (IsUnder(d, dataPath) || string.Equals(d, dataPath, StringComparison.OrdinalIgnoreCase)) continue;
                        try { Directory.Delete(d, false); }
                        catch (Exception) { }
                    }
                    try { File.Delete(System.Reflection.Assembly.GetExecutingAssembly().Location); }
                    catch (Exception) { }
                }
            }
            catch (Exception)
            {
                // best effort: final retry of stray files
                try { File.Delete(System.Reflection.Assembly.GetExecutingAssembly().Location); }
                catch (Exception) { }
            }
        }

        static bool IsUnder(string path, string baseDir)
        {
            if (string.Equals(path, baseDir, StringComparison.OrdinalIgnoreCase)) return true;
            return path.StartsWith(baseDir + System.IO.Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
        }
    }
}
