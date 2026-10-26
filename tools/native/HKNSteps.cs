// HKN Dentaire - installer steps (no forms). Used by HKNSetupUI.cs.
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Text;
using Microsoft.Win32;

namespace HKN
{
    internal static class Steps
    {
        // 1: extract payload
        public static string ExtractZip(string rootDir)
        {
            string err;
            try
            {
                byte[] zip = Payload.Slice();
                using (var ms = new MemoryStream(zip))
                using (var archive = new ZipArchive(ms, ZipArchiveMode.Read))
                {
                    foreach (var entry in archive.Entries)
                    {
                        string target = Path.Combine(rootDir, entry.FullName.Replace('/', Path.DirectorySeparatorChar));
                        if (target.StartsWith(Path.Combine(rootDir, "data") + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                            continue; // preserve existing data on repair
                        string safe = Path.GetFullPath(target);
                        if (!safe.StartsWith(rootDir + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                            return "Entrée non sécurisée: " + entry.FullName;
                        string dir = Path.GetDirectoryName(safe);
                        if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir)) Directory.CreateDirectory(dir);
                        if (entry.FullName.EndsWith("/", StringComparison.Ordinal) || Path.GetFileName(safe) == "")
                            continue;
                        using (var es = entry.Open())
                        using (var ts = File.Create(safe))
                            es.CopyTo(ts);
                    }
                }
                return null;
            }
            catch (Exception ex)
            {
                try { using (var sw = new StreamWriter(Path.Combine(Path.GetTempPath(), "hkn_setup_last_error.txt"))) sw.Write(ex.ToString()); } catch { }
                err = "Extraction échouée: " + ex.Message;
                return err;
            }
        }

        // 2: copy license file
        public static void CopyLicense(string srcLic, string rootDir)
        {
            if (string.IsNullOrEmpty(srcLic) || !File.Exists(srcLic)) return;
            Directory.CreateDirectory(Path.Combine(rootDir, "data"));
            File.Copy(srcLic, Path.Combine(rootDir, "data", "clinic.lic"), true);
        }

        // 3: initialize prod database. Returns output text or throws.
        public static string InitProd(string rootDir, string user, string pass, string fullName, bool reset)
        {
            var psi = new ProcessStartInfo
            {
                FileName = Path.Combine(rootDir, "runtime", "python.exe"),
                Arguments = "app\\cli.py init-prod" + (reset ? " --force" : ""),
                CreateNoWindow = true,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                WorkingDirectory = rootDir,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
            };
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            psi.EnvironmentVariables["CLINIC_INIT_USERNAME"] = user;
            psi.EnvironmentVariables["CLINIC_INIT_PASSWORD"] = pass;
            psi.EnvironmentVariables["CLINIC_INIT_FULLNAME"] = fullName;
            using (var p = Process.Start(psi))
            {
                string so = p.StandardOutput.ReadToEnd();
                string se = p.StandardError.ReadToEnd();
                p.WaitForExit(120000);
                if (p.ExitCode != 0)
                    throw new IOException("init-prod a échoué (code " + p.ExitCode + "):\n" + se + "\n" + so);
                return so;
            }
        }

        // 6: installation identifier for the license page (cli print-installation-id)
        public static string ReadInstallationIdAt(string rootDir)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = Path.Combine(rootDir, "runtime", "python.exe"),
                    Arguments = "app\\cli.py print-installation-id --json",
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    WorkingDirectory = rootDir,
                };
                using (var p = Process.Start(psi))
                {
                    string outp = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(60000);
                    int hit = outp.IndexOf("\"installation\"", StringComparison.OrdinalIgnoreCase);
                    if (hit < 0) return null;
                    int start = outp.IndexOf('"', hit + 14);
                    int end = outp.IndexOf('"', start + 1);
                    if (start < 0 || end < 0) return null;
                    return outp.Substring(start + 1, end - start - 1);
                }
            }
            catch (Exception)
            {
                return null;
            }
        }

        // 7: shortcuts via WScript.Shell, late-bound reflection only.
        public static void MakeShortcut(string lnkPath, string targetPath, string args, string workdir, string iconPath, int iconIndex)
        {
            object shell = Activator.CreateInstance(
                Type.GetTypeFromProgID("WScript.Shell", true));
            object sc = shell.GetType().InvokeMember("CreateShortcut",
                System.Reflection.BindingFlags.InvokeMethod, null, shell, new object[] { lnkPath });
            SetCom(sc, "TargetPath", targetPath);
            if (!string.IsNullOrEmpty(args)) SetCom(sc, "Arguments", args);
            if (!string.IsNullOrEmpty(workdir)) SetCom(sc, "WorkingDirectory", workdir);
            if (!string.IsNullOrEmpty(iconPath)) SetCom(sc, "IconLocation", iconPath + "," + iconIndex);
            SetCom(sc, "Description", "Application de gestion de clinique dentaire");
            sc.GetType().InvokeMember("Save", System.Reflection.BindingFlags.InvokeMethod, null, sc, new object[] { null });
        }

        static void SetCom(object o, string prop, string val)
        {
            o.GetType().InvokeMember(prop, System.Reflection.BindingFlags.SetProperty, null, o, new object[] { val });
        }

        public static void MakeShortcuts(string rootDir, bool desktop)
        {
            string scriptsDir = Path.Combine(rootDir, "scripts");
            string exe = Path.Combine(scriptsDir, "HKN Dentaire.exe");
            string icon = Path.Combine(rootDir, "branding", "app.ico");
            string desk = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "HKN Dentaire.lnk");
            string sm = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "Microsoft", "Windows", "Start Menu", "Programs", "HKN Dentaire.lnk");
            if (desktop) MakeShortcut(desk, exe, "", scriptsDir, icon, 0);
            MakeShortcut(sm, exe, "", scriptsDir, icon, 0);
        }

        // 5: uninstall registry (HKCU, no admin needed)
        public static void RegisterUninstall(string rootDir)
        {
            try
            {
                string keyPath = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\HKN Dentaire";
                using (var key = Registry.CurrentUser.CreateSubKey(keyPath, true))
                {
                    key.SetValue("DisplayName", "HKN Dentaire");
                    key.SetValue("DisplayVersion", "1.0.0");
                    key.SetValue("Publisher", "HKN Dentaire");
                    key.SetValue("InstallLocation", rootDir);
                    key.SetValue("DisplayIcon", Path.Combine(rootDir, "scripts", "HKN Dentaire.exe"));
                    string unins = Path.Combine(rootDir, "scripts", "HKN Dentaire.exe");
                    key.SetValue("UninstallString", "\"" + unins + "\" /uninstall");
                    key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                    key.SetValue("NoRemove", 0, RegistryValueKind.DWord);
                    key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                    key.SetValue("EstimatedSize", 200 * 1024, RegistryValueKind.DWord);
                }
            }
            catch (Exception) { /* cosmetic registry, optional */ }
        }

        // 6: LAN firewall rule (needs admin, run elevated at the end)
        public static void AllowLan()
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe",
                    Arguments = "/c netsh advfirewall firewall delete rule name=\"HKN Dentaire LAN\" & netsh advfirewall firewall add rule name=\"HKN Dentaire LAN\" dir=in action=allow protocol=TCP localport=8000 profile=private",
                    Verb = "runas", // elevation prompt from the user's confirmation click
                    CreateNoWindow = true,
                };
                Process.Start(psi);
            }
            catch (Exception) { /* skipped by user */ }
        }

        // 7: kill instances of a previous install
        public static void KillProcessesUnder(string rootDir)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = Environment.GetEnvironmentVariable("ComSpec") ?? "cmd.exe",
                    Arguments = "/c call \"" + Path.Combine(rootDir, "scripts", "stop.bat") + "\"",
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    WorkingDirectory = rootDir,
                };
                using (var p = Process.Start(psi)) p.WaitForExit(45000);
            }
            catch (Exception) { }
            UninstallRunner.KillAll(rootDir);
        }
    }
}
