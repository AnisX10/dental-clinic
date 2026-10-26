// HKN Dentaire - installation + uninstall logic (no UI), compiled into the Setup exe.
// Payload layout produced by tools/build_native.py:
//   [ZIP bytes][ 8-byte little-endian ZIP length ][ ASCII "HKNPAYLOAD!" ]  <- file tail
using System;
using System.IO;
using System.IO.Compression;
using System.Text;

namespace HKN
{
    internal static class Payload
    {
        const string Marker = "HKNPAYLOAD!";

        public static byte[] Slice()
        {
            string self = System.Reflection.Assembly.GetExecutingAssembly().Location;
            using (var fs = File.OpenRead(self))
            {
                if (fs.Length < 64 + 8 + Marker.Length)
                    throw new IOException("Le fichier d'installation est incomplet.");
                fs.Seek(-64, SeekOrigin.End);
                var tail = new byte[64];
                fs.Read(tail, 0, 64);
                string tailStr = Encoding.ASCII.GetString(tail);
                int hit = tailStr.IndexOf(Marker, StringComparison.Ordinal);
                if (hit < 0)
                    throw new IOException("Marqueur d'installation introuvable.");
                int lenIdx = hit + Marker.Length;
                long payloadLen = BitConverter.ToInt64(tail, lenIdx);
                if (payloadLen <= 0 || payloadLen > fs.Length)
                    throw new IOException("Le fichier d'installation est corrompu.");
                long zipStart = fs.Length - 64 + hit - payloadLen;
                if (zipStart < 0)
                    throw new IOException("Le fichier d'installation est corrompu.");
                var buf = new byte[payloadLen];
                fs.Seek(zipStart, SeekOrigin.Begin);
                int readTotal = 0;
                while (readTotal < payloadLen)
                {
                    int n = fs.Read(buf, readTotal, (int)(payloadLen - readTotal));
                    if (n <= 0) break;
                    readTotal += n;
                }
                if (readTotal != payloadLen)
                    throw new IOException("Lecture du contenu d'installation échouée.");
                return buf;
            }
        }

        public static string ZipLengthSignature()
        {
            // big files: peek only
            string self = System.Reflection.Assembly.GetExecutingAssembly().Location;
            return new FileInfo(self).Length.ToString();
        }
    }
}
