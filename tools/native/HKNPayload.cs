// HKN Dentaire - payload access, compiled into the Setup exe.
// Payload layout produced by tools/build_native.py (appended to the PE file):
//   [ZIP bytes][32-byte SHA256 of ZIP][8-byte little-endian ZIP length][ASCII "HKNPAYLOAD2"]
// Authenticode signing (signtool) appends a certificate table AFTER that, so
// the payload end is located through the PE security directory, not the file end.
using System;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;

namespace HKN
{
    internal static class Payload
    {
        const string Marker = "HKNPAYLOAD2";
        static byte[] _cache;

        // Where the payload trailer ends: start of the Authenticode certificate
        // table when the exe is signed, otherwise the end of the file.
        static long PayloadLimit(FileStream fs)
        {
            try
            {
                var br = new BinaryReader(fs);
                fs.Seek(0x3C, SeekOrigin.Begin);
                int peOff = br.ReadInt32();
                fs.Seek(peOff, SeekOrigin.Begin);
                if (br.ReadUInt32() != 0x00004550) return fs.Length; // "PE\0\0"
                long opt = peOff + 4 + 20;                            // optional header
                fs.Seek(opt, SeekOrigin.Begin);
                ushort magic = br.ReadUInt16();
                long dirs = opt + (magic == 0x20b ? 112 : 96);        // data directories
                fs.Seek(dirs + 4 * 8, SeekOrigin.Begin);              // IMAGE_DIRECTORY_ENTRY_SECURITY
                uint certOff = br.ReadUInt32();
                uint certSize = br.ReadUInt32();
                if (certOff != 0 && certSize != 0 && certOff <= fs.Length) return certOff;
            }
            catch (Exception) { }
            return fs.Length;
        }

        public static byte[] Slice()
        {
            if (_cache != null) return _cache;
            string self = System.Reflection.Assembly.GetExecutingAssembly().Location;
            using (var fs = File.OpenRead(self))
            {
                long limit = PayloadLimit(fs);
                int window = (int)Math.Min(128, limit);
                if (window < 32 + 8 + Marker.Length)
                    throw new IOException("Le fichier d'installation est incomplet.");
                // signtool pads to an 8-byte boundary before the certificate:
                // search the marker in the last bytes before the limit.
                fs.Seek(limit - window, SeekOrigin.Begin);
                var tail = new byte[window];
                ReadFully(fs, tail, window);
                int hit = Encoding.ASCII.GetString(tail).LastIndexOf(Marker, StringComparison.Ordinal);
                if (hit < 32 + 8)
                    throw new IOException("Marqueur d'installation introuvable (fichier d'installation incomplet ou modifié).");
                long markerPos = limit - window + hit;
                long payloadLen = BitConverter.ToInt64(tail, hit - 8);
                byte[] expected = new byte[32];
                Array.Copy(tail, hit - 8 - 32, expected, 0, 32);
                long zipStart = markerPos - 8 - 32 - payloadLen;
                if (payloadLen <= 0 || payloadLen > int.MaxValue || zipStart < 0)
                    throw new IOException("Le fichier d'installation est corrompu.");
                var buf = new byte[payloadLen];
                fs.Seek(zipStart, SeekOrigin.Begin);
                ReadFully(fs, buf, (int)payloadLen);
                byte[] actual;
                using (var sha = SHA256.Create()) actual = sha.ComputeHash(buf);
                for (int i = 0; i < 32; i++)
                    if (actual[i] != expected[i])
                        throw new IOException("Le fichier d'installation est corrompu (somme de contrôle SHA256 invalide). " +
                                              "Téléchargez-le ou copiez-le à nouveau.");
                _cache = buf;
                return buf;
            }
        }

        static void ReadFully(Stream s, byte[] buf, int count)
        {
            int total = 0;
            while (total < count)
            {
                int n = s.Read(buf, total, count - total);
                if (n <= 0) throw new IOException("Lecture du contenu d'installation échouée.");
                total += n;
            }
        }

        // Small text entry of the payload (e.g. "VERSION"), or null if absent.
        public static string ReadText(string entryName)
        {
            using (var ms = new MemoryStream(Slice()))
            using (var archive = new ZipArchive(ms, ZipArchiveMode.Read))
            {
                var e = archive.GetEntry(entryName);
                if (e == null) return null;
                using (var sr = new StreamReader(e.Open(), Encoding.UTF8)) return sr.ReadToEnd();
            }
        }
    }
}
