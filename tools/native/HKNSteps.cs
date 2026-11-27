// HKN Dentaire - installer steps (no forms). Used by HKNSetupUI.cs.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using Microsoft.Win32;

namespace HKN
{
    internal static class Steps
    {
        // Install manifest ("<sha256>  <relative/posix/path>" per line), shipped
        // in the payload by tools/hkn_packaging.py. Uninstall deletes only the
        // files it lists (plus the known application directories).
        public const string ManifestName = "MANIFEST.txt";
        public const string VersionName = "VERSION";
        public const string StagingDirName = "_upgrade_staging";
        public const string OldDirName = "_upgrade_old";

        // Application directories replaced as a whole on install/upgrade, so
        // removed files and old migrations never linger.
        public static readonly string[] AppDirs = { "backend", Path.Combine("frontend", ".output"), "runtime", "scripts" };

        // ------------------------------------------------------------ logging
        public static readonly string LogPath = Path.Combine(Path.GetTempPath(), "hkn_setup.log");
        static readonly object LogLock = new object();

        public static void Log(string line)
        {
            try
            {
                lock (LogLock)
                    File.AppendAllText(LogPath, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + line + "\r\n", new UTF8Encoding(false));
            }
            catch (Exception) { }
        }

        // ------------------------------------------------------------ versions
        public static string PayloadVersion()
        {
            try { return FirstLine(Payload.ReadText(VersionName)); }
            catch (Exception ex) { Log("payload VERSION illisible: " + ex.Message); return null; }
        }

        public static string InstalledVersion(string root)
        {
            try
            {
                string p = Path.Combine(root, VersionName);
                return File.Exists(p) ? FirstLine(File.ReadAllText(p)) : null;
            }
            catch (Exception) { return null; }
        }

        static string FirstLine(string text)
        {
            if (text == null) return null;
            string v = text.Replace("\r", "").Split('\n')[0].Trim().TrimStart('﻿');
            return v.Length == 0 ? null : v;
        }

        // Numeric dotted comparison ("1.10.0" > "1.9.2"); non-digits ignored.
        public static int CompareVersions(string a, string b)
        {
            int[] x = ParseVersion(a), y = ParseVersion(b);
            for (int i = 0; i < 4; i++)
                if (x[i] != y[i]) return x[i].CompareTo(y[i]);
            return 0;
        }

        static int[] ParseVersion(string v)
        {
            var r = new int[4];
            string[] parts = (v ?? "").Split('.');
            for (int i = 0; i < 4 && i < parts.Length; i++)
            {
                string digits = new string(parts[i].TakeWhile(char.IsDigit).ToArray());
                int n;
                r[i] = int.TryParse(digits, out n) ? n : 0;
            }
            return r;
        }

        // ------------------------------------------------------------ 1: files
        // Extract the payload to <root>\_upgrade_staging, then swap the app
        // directories in (old ones are moved aside first, so a locked file aborts
        // cleanly with the previous version intact). data\ is never touched.
        public static string InstallFiles(string rootDir, Action<string> progress)
        {
            try
            {
                string root = NormalizeRoot(rootDir);
                string staging = Path.Combine(root, StagingDirName);
                string old = Path.Combine(root, OldDirName);
                DeleteTree(staging);
                DeleteTree(old);
                Directory.CreateDirectory(staging);

                var newRels = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                bool payloadHasManifest = false;
                byte[] zip = Payload.Slice(); // verifies the SHA256 first
                Log("payload: " + zip.Length + " octets, SHA256 OK");
                using (var ms = new MemoryStream(zip))
                using (var archive = new ZipArchive(ms, ZipArchiveMode.Read))
                {
                    int i = 0, total = archive.Entries.Count;
                    foreach (var entry in archive.Entries)
                    {
                        i++;
                        if (progress != null && i % 500 == 0) progress("        … " + i + " / " + total + " fichiers");
                        string rel = entry.FullName.Replace('\\', '/');
                        if (rel.EndsWith("/", StringComparison.Ordinal)) continue;
                        if (rel.StartsWith("data/", StringComparison.OrdinalIgnoreCase)) continue; // never ship over data
                        string safe = Path.GetFullPath(Path.Combine(staging, rel.Replace('/', Path.DirectorySeparatorChar)));
                        if (!safe.StartsWith(staging + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                            return "Entrée non sécurisée dans le paquet: " + entry.FullName;
                        Directory.CreateDirectory(Path.GetDirectoryName(safe));
                        using (var es = entry.Open())
                        using (var ts = File.Create(safe))
                            es.CopyTo(ts);
                        if (string.Equals(rel, ManifestName, StringComparison.OrdinalIgnoreCase)) payloadHasManifest = true;
                        else newRels.Add(rel);
                    }
                }

                var oldRels = ReadManifestRels(Path.Combine(root, ManifestName));

                // swap application directories
                var movedAside = new List<string>();
                try
                {
                    foreach (string d in AppDirs)
                    {
                        string cur = Path.Combine(root, d);
                        if (!Directory.Exists(cur)) continue;
                        string dst = Path.Combine(old, d);
                        Directory.CreateDirectory(Path.GetDirectoryName(dst));
                        Directory.Move(cur, dst);
                        movedAside.Add(d);
                    }
                }
                catch (Exception ex)
                {
                    RestoreMovedAside(root, old, movedAside);
                    Log("échange impossible: " + ex);
                    return "Des fichiers de l'installation actuelle sont encore utilisés (" + ex.Message + ").\n" +
                           "Fermez HKN Dentaire (icône près de l'horloge) puis relancez l'installation. Rien n'a été modifié.";
                }
                try
                {
                    foreach (string d in AppDirs)
                    {
                        string src = Path.Combine(staging, d);
                        if (!Directory.Exists(src)) continue;
                        string dst = Path.Combine(root, d);
                        Directory.CreateDirectory(Path.GetDirectoryName(dst));
                        Directory.Move(src, dst);
                    }
                }
                catch (Exception ex)
                {
                    foreach (string d in AppDirs)
                    {
                        // put back the previous version of anything not replaced
                        string dst = Path.Combine(root, d), back = Path.Combine(old, d);
                        try { if (!Directory.Exists(dst) && Directory.Exists(back)) Directory.Move(back, dst); }
                        catch (Exception) { }
                    }
                    Log("mise en place impossible: " + ex);
                    return "Mise en place des nouveaux fichiers échouée: " + ex.Message;
                }

                // remaining payload files (branding, docs, VERSION, MANIFEST.txt)
                foreach (string f in Directory.EnumerateFiles(staging, "*", SearchOption.AllDirectories).ToList())
                {
                    string rel = f.Substring(staging.Length + 1);
                    string dst = Path.Combine(root, rel);
                    Directory.CreateDirectory(Path.GetDirectoryName(dst));
                    File.Copy(f, dst, true);
                }

                // files the previous version installed outside the app dirs and
                // that this version no longer ships (never under data\)
                foreach (string rel in oldRels)
                {
                    if (newRels.Contains(rel) || rel.StartsWith("data/", StringComparison.OrdinalIgnoreCase)) continue;
                    if (AppDirs.Any(d => rel.StartsWith(d.Replace('\\', '/') + "/", StringComparison.OrdinalIgnoreCase))) continue;
                    try
                    {
                        string full = Path.GetFullPath(Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar)));
                        if (full.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) && File.Exists(full))
                        {
                            File.Delete(full);
                            Log("fichier obsolète supprimé: " + rel);
                        }
                    }
                    catch (Exception) { }
                }

                if (!payloadHasManifest) WriteManifest(root, newRels.ToList());
                DeleteTree(staging);
                DeleteTree(old);
                return null;
            }
            catch (Exception ex)
            {
                Log("extraction: " + ex);
                return "Extraction échouée: " + ex.Message;
            }
        }

        static void RestoreMovedAside(string root, string old, List<string> moved)
        {
            foreach (string d in moved)
            {
                try { Directory.Move(Path.Combine(old, d), Path.Combine(root, d)); }
                catch (Exception ex) { Log("restauration de " + d + " impossible: " + ex.Message); }
            }
        }

        public static string NormalizeRoot(string rootDir)
        {
            string root = Path.GetFullPath(rootDir);
            if (!string.Equals(root, Path.GetPathRoot(root), StringComparison.OrdinalIgnoreCase))
                root = root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            return root;
        }

        static void DeleteTree(string dir)
        {
            try { if (Directory.Exists(dir)) Directory.Delete(dir, true); }
            catch (Exception ex) { Log("suppression de " + dir + " incomplète: " + ex.Message); }
        }

        static List<string> ReadManifestRels(string path)
        {
            var rels = new List<string>();
            try
            {
                if (!File.Exists(path)) return rels;
                foreach (string line in File.ReadAllLines(path, Encoding.UTF8))
                {
                    if (line.Length < 67 || line[64] != ' ' || line[65] != ' ') continue;
                    if (!line.Take(64).All(Uri.IsHexDigit)) continue;
                    string rel = line.Substring(66).Trim();
                    if (rel.Length > 0 && !rel.Split('/', '\\').Any(s => s == "..") && rel.IndexOf(':') < 0) rels.Add(rel);
                }
            }
            catch (Exception) { }
            return rels;
        }

        static void WriteManifest(string rootDir, List<string> rels)
        {
            var sb = new StringBuilder();
            sb.Append("HKN Dentaire - manifeste des fichiers\nsha256  chemin\n\n");
            using (var sha = System.Security.Cryptography.SHA256.Create())
            {
                foreach (string rel in rels)
                {
                    string hex;
                    using (var fs = File.OpenRead(Path.Combine(rootDir, rel.Replace('/', Path.DirectorySeparatorChar))))
                        hex = BitConverter.ToString(sha.ComputeHash(fs)).Replace("-", "").ToLowerInvariant();
                    sb.Append(hex).Append("  ").Append(rel).Append('\n');
                }
            }
            File.WriteAllText(Path.Combine(rootDir, ManifestName), sb.ToString(), new UTF8Encoding(false));
        }

        // ------------------------------------------------------------ licence
        static string NormalizeKey(string keyText)
        {
            if (string.IsNullOrWhiteSpace(keyText)) return "";
            var sb = new StringBuilder();
            foreach (char c in keyText.Trim()) if (!char.IsWhiteSpace(c)) sb.Append(c);
            return sb.ToString();
        }

        // Verify with the app's own verifier (app.licensing.service.verify_key_text).
        // Returns null when the key is valid, otherwise a French reason.
        public static string VerifyKey(string rootDir, string keyText)
        {
            string key = NormalizeKey(keyText);
            if (key.Length == 0) return null;
            const string script =
                "import os, sys; sys.path.insert(0, os.environ['HKN_BACKEND']); " +
                "from app.licensing.service import verify_key_text; " +
                "s = verify_key_text(sys.stdin.read()); print('HKNKEY:' + s.reason)";
            var psi = new ProcessStartInfo
            {
                FileName = Path.Combine(rootDir, "runtime", "python.exe"),
                Arguments = "-c \"" + script + "\"",
                CreateNoWindow = true,
                UseShellExecute = false,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                WorkingDirectory = rootDir,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
            };
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            psi.EnvironmentVariables["HKN_BACKEND"] = Path.Combine(rootDir, "backend");
            try
            {
                using (var p = Process.Start(psi))
                {
                    var so = p.StandardOutput.ReadToEndAsync();
                    var se = p.StandardError.ReadToEndAsync();
                    p.StandardInput.Write(key);
                    p.StandardInput.Close();
                    if (!p.WaitForExit(60000)) { try { p.Kill(); } catch (Exception) { } return "vérification impossible (délai dépassé)"; }
                    string outp = so.Result;
                    int hit = outp.LastIndexOf("HKNKEY:", StringComparison.Ordinal);
                    if (hit < 0) { Log("vérification licence: " + se.Result); return "vérification impossible (voir " + LogPath + ")"; }
                    string reason = outp.Substring(hit + 7).Trim();
                    Log("vérification licence: " + reason);
                    switch (reason)
                    {
                        case "ok": return null;
                        case "malformed": return "clé mal formée (incomplète ou mal copiée)";
                        case "invalid_signature": return "signature invalide (clé modifiée ou non émise par HKN Dentaire)";
                        default: return reason;
                    }
                }
            }
            catch (Exception ex)
            {
                Log("vérification licence: " + ex);
                return "vérification impossible: " + ex.Message;
            }
        }

        // 2: save the pasted licence key
        public static void SaveKey(string keyText, string rootDir)
        {
            string key = NormalizeKey(keyText);
            if (key.Length == 0) return;
            Directory.CreateDirectory(Path.Combine(rootDir, "data"));
            File.WriteAllText(Path.Combine(rootDir, "data", "clinic.key"), key + "\n", new UTF8Encoding(false));
        }

        // ------------------------------------------------------------ 3: init-prod
        // 10-minute budget with progress. On failure: stop the database and, if
        // this run created data\pgdata, delete it so a retry starts clean.
        public static string InitProd(string rootDir, string user, string pass, string fullName, Action<string> progress)
        {
            string pgdata = Path.Combine(rootDir, "data", "pgdata");
            bool pgdataExisted = Directory.Exists(pgdata);
            var psi = new ProcessStartInfo
            {
                FileName = Path.Combine(rootDir, "runtime", "python.exe"),
                Arguments = "\"" + Path.Combine(rootDir, "backend", "app", "cli.py") + "\" init-prod",
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
            string failure = null, so = "", se = "";
            try
            {
                using (var p = Process.Start(psi))
                {
                    var stdout = p.StandardOutput.ReadToEndAsync();
                    var stderr = p.StandardError.ReadToEndAsync();
                    var sw = Stopwatch.StartNew();
                    while (!p.WaitForExit(10000))
                    {
                        if (sw.Elapsed > TimeSpan.FromMinutes(10))
                        {
                            try { p.Kill(); } catch (Exception) { }
                            p.WaitForExit(15000);
                            failure = "l'initialisation a dépassé le délai de 10 minutes";
                            break;
                        }
                        if (progress != null) progress("        … initialisation en cours (" + (int)sw.Elapsed.TotalSeconds + " s)");
                    }
                    if (failure == null)
                    {
                        so = stdout.Result;
                        se = stderr.Result;
                        Log("init-prod code " + p.ExitCode + "\n" + so + "\n" + se);
                        if (p.ExitCode != 0)
                            failure = "init-prod a échoué (code " + p.ExitCode + "):\n" + Tail(se + "\n" + so, 800);
                        else if (so.IndexOf("already exists", StringComparison.OrdinalIgnoreCase) >= 0 ||
                                 so.IndexOf("no additional owner", StringComparison.OrdinalIgnoreCase) >= 0)
                            failure = "un compte propriétaire existe déjà dans cette base de données : le mot de passe que vous " +
                                      "venez de saisir n'a PAS été appliqué. Utilisez le compte existant (ou « reset_password.bat »).";
                    }
                }
            }
            catch (Exception ex)
            {
                failure = "init-prod n'a pas pu être lancé: " + ex.Message;
            }
            if (failure == null) return so;

            Log("init-prod: échec -> arrêt de la base" + (pgdataExisted ? "" : " et suppression de data\\pgdata"));
            Common.GracefulStop(rootDir);
            if (!pgdataExisted && !UninstallRunner.HasPostgresUnder(rootDir)) DeleteTree(pgdata);
            throw new IOException(failure);
        }

        static string Tail(string s, int n)
        {
            s = (s ?? "").Trim();
            return s.Length <= n ? s : "…" + s.Substring(s.Length - n);
        }

        // installation identifier for the license page (cli print-installation-id)
        public static string ReadInstallationIdAt(string rootDir)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = Path.Combine(rootDir, "runtime", "python.exe"),
                    Arguments = "\"" + Path.Combine(rootDir, "backend", "app", "cli.py") + "\" print-installation-id --json",
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    WorkingDirectory = rootDir,
                };
                using (var p = Process.Start(psi))
                {
                    var stdout = p.StandardOutput.ReadToEndAsync();
                    if (!p.WaitForExit(60000))
                    {
                        try { p.Kill(); } catch (Exception) { }
                        return null;
                    }
                    string outp = stdout.Result;
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

        // ------------------------------------------------------------ shortcuts
        // via WScript.Shell, late-bound reflection only.
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
            sc.GetType().InvokeMember("Save", System.Reflection.BindingFlags.InvokeMethod, null, sc, new object[0]); // Save() takes no arguments
        }

        static void SetCom(object o, string prop, string val)
        {
            o.GetType().InvokeMember(prop, System.Reflection.BindingFlags.SetProperty, null, o, new object[] { val });
        }

        // Returns a list of warnings (empty = all shortcuts created).
        public static List<string> MakeShortcuts(string rootDir, bool desktop)
        {
            var warnings = new List<string>();
            string scriptsDir = Path.Combine(rootDir, "scripts");
            string exe = Path.Combine(scriptsDir, "HKN Dentaire.exe");
            string icon = Path.Combine(rootDir, "branding", "app.ico");
            string desk = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "HKN Dentaire.lnk");
            string sm = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "Microsoft", "Windows", "Start Menu", "Programs", "HKN Dentaire.lnk");
            if (desktop)
            {
                try { MakeShortcut(desk, exe, "", scriptsDir, icon, 0); }
                catch (Exception ex) { warnings.Add("raccourci du Bureau non créé (" + Inner(ex) + ")"); Log("raccourci bureau: " + ex); }
            }
            try { MakeShortcut(sm, exe, "", scriptsDir, icon, 0); }
            catch (Exception ex) { warnings.Add("raccourci du menu Démarrer non créé (" + Inner(ex) + ")"); Log("raccourci menu: " + ex); }
            return warnings;
        }

        static string Inner(Exception ex)
        {
            while (ex.InnerException != null) ex = ex.InnerException;
            return ex.Message;
        }

        // ------------------------------------------------------------ registry
        public static void RegisterUninstall(string rootDir, string version)
        {
            try
            {
                string keyPath = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\HKN Dentaire";
                using (var key = Registry.CurrentUser.CreateSubKey(keyPath, true))
                {
                    key.SetValue("DisplayName", "HKN Dentaire");
                    key.SetValue("DisplayVersion", string.IsNullOrEmpty(version) ? BuildInfo.Version : version);
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
            catch (Exception ex) { Log("registre: " + ex.Message); }
        }

        public static string RegisteredInstallLocation()
        {
            try
            {
                using (var key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\HKN Dentaire", false))
                {
                    string v = key == null ? null : key.GetValue("InstallLocation") as string;
                    return string.IsNullOrWhiteSpace(v) ? null : v.Trim();
                }
            }
            catch (Exception) { return null; }
        }

        // ------------------------------------------------------------ network
        // data\config.json = {"port": N, "lan": bool}. An existing port is kept
        // (upgrade); otherwise 8000, or the first free port after it.
        public static int WriteConfig(string rootDir, bool lan)
        {
            int port;
            string cfg = Common.ConfigPath(rootDir);
            bool hadPort = File.Exists(cfg) && System.Text.RegularExpressions.Regex.IsMatch(File.ReadAllText(cfg), "\"port\"\\s*:\\s*\\d+");
            if (hadPort) port = Common.ReadPort(rootDir);
            else
            {
                port = Common.DefaultPort;
                for (int p = Common.DefaultPort; p < Common.DefaultPort + 100; p++)
                    if (IsPortFree(p)) { port = p; break; }
            }
            Directory.CreateDirectory(Path.GetDirectoryName(cfg));
            File.WriteAllText(cfg, "{\"port\": " + port + ", \"lan\": " + (lan ? "true" : "false") + "}\n", new UTF8Encoding(false));
            Log("config.json: port " + port + ", lan " + lan);
            return port;
        }

        static bool IsPortFree(int port)
        {
            TcpListener l = null;
            try
            {
                l = new TcpListener(IPAddress.Any, port);
                l.ExclusiveAddressUse = true;
                l.Start();
                return true;
            }
            catch (SocketException) { return false; }
            finally { if (l != null) try { l.Stop(); } catch (Exception) { } }
        }

        // ------------------------------------------------------------ stop
        // Stop a previous install before replacing its files: tray first (so it
        // cannot restart the server), then a clean PostgreSQL stop, then leftovers.
        public static void KillProcessesUnder(string rootDir)
        {
            KillTrayUnder(rootDir);
            Common.GracefulStop(rootDir);
            UninstallRunner.KillAll(rootDir);
            if (UninstallRunner.HasPostgresUnder(rootDir))
                throw new IOException("PostgreSQL ne s'est pas arrêté proprement. Relancez l'installation après avoir fermé HKN Dentaire.");
        }

        static void KillTrayUnder(string rootDir)
        {
            string exe = Path.Combine(NormalizeRoot(rootDir), "scripts", "HKN Dentaire.exe");
            foreach (var proc in Process.GetProcessesByName("HKN Dentaire"))
            {
                try
                {
                    string image = null;
                    try { image = Path.GetFullPath(proc.MainModule.FileName); } catch (Exception) { }
                    if (image != null && string.Equals(image, exe, StringComparison.OrdinalIgnoreCase))
                    {
                        Log("arrêt de l'icône HKN Dentaire (pid " + proc.Id + ")");
                        proc.Kill();
                        proc.WaitForExit(5000);
                    }
                }
                catch (Exception) { }
                finally { proc.Dispose(); }
            }
        }
    }
}
