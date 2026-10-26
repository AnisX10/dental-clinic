"""Render INSTALLATION_GUIDE PDF from a styled HTML wrapper (Chrome headless)."""
import base64
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(r"C:\Users\TL\.local\share\opencode\tmp")
ICON = (ROOT / "branding" / "icon-512.png").read_bytes()
ICON_B64 = base64.b64encode(ICON).decode("ascii")

HTML = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 18mm 16mm; }
  body { font-family: "Segoe UI", Arial, sans-serif; color: #1c2333; font-size: 10.5pt; line-height: 1.45; }
  h1 { font-size: 21pt; color: #002AA0; margin: 0 0 2mm 0; }
  .cover-sub { color: #55607a; font-size: 11pt; margin-bottom: 6mm; }
  .cover { text-align: center; margin-top: 55mm; page-break-after: always; }
  .cover img { width: 34mm; }
  h2 { font-size: 13.5pt; color: #2E6BFF; border-bottom: 1.5pt solid #2E6BFF; padding-bottom: 1.5mm; margin: 8mm 0 3mm 0; page-break-after: avoid; }
  h3 { font-size: 11pt; color: #1c2333; margin: 5mm 0 2mm 0; page-break-after: avoid; }
  table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm 0; page-break-inside: avoid; }
  th { background: #eef3ff; color: #002AA0; text-align: left; padding: 2mm 3mm; border: 0.5pt solid #c9d6f5; }
  td { padding: 2mm 3mm; border: 0.5pt solid #c9d6f5; vertical-align: top; }
  code { font-family: Consolas, monospace; background: #f2f4fa; padding: 0.5mm 1.2mm; border-radius: 2px; font-size: 9.5pt; }
  .note { background: #fff8e6; border-left: 3pt solid #f0b429; padding: 2.5mm 4mm; margin: 3mm 0; }
  .tip { background: #eefaff; border-left: 3pt solid #2E6BFF; padding: 2.5mm 4mm; margin: 3mm 0; }
  ol li, ul li { margin-bottom: 1.5mm; }
  .step b { color: #002AA0; }
  footer { color: #8b93a8; font-size: 8.5pt; border-top: 0.5pt solid #dfe4ef; padding-top: 2mm; margin-top: 10mm; }
</style>
</head>
<body>

<div class="cover">
  <img src="data:image/png;base64,__ICON__" alt="">
  <h1>HKN Dentaire</h1>
  <div class="cover-sub">Guide d'installation et d'utilisation<br>Version 1.0.0 &mdash; Octobre 2026</div>
</div>

<h2>1. Ce que vous recevez</h2>
<table>
  <tr><th>Livraison</th><th>Contenu</th></tr>
  <tr><td><code>HKN Dentaire Setup.exe</code></td><td>Programme d'installation en un seul fichier (recommandé)</td></tr>
  <tr><td><code>HKN Dentaire.zip</code></td><td>Version portable (alternative)</td></tr>
  <tr><td><code>VotreClinique.lic</code></td><td>Fichier de licence de votre clinique (fourni séparément par votre revendeur)</td></tr>
</table>
<div class="note"><b>Aucun accès à Internet n'est requis.</b> Tout est intégré : application, base de données, environnements d'exécution.</div>

<h2>2. Installation — Setup.exe (recommandé)</h2>
<ol>
  <li>Double-cliquez sur <b>HKN Dentaire Setup.exe</b>.</li>
</ol>
<div class="tip"><b>Windows a protégé votre ordinateur ?</b> (SmartScreen) Cliquez sur <b>Informations complémentaires</b> puis <b>Exécuter quand même</b>. Ce message apparaît car le programme n'est pas signé par une grande société ; il provient de votre revendeur. Si votre antivirus pose une question, vérifiez la source puis autorisez.</div>
<ol start="2">
  <li>Suivez l'assistant :
    <ul>
      <li><b>Licence</b> : le programme détecte automatiquement un fichier <code>.lic</code> situé à côté du Setup. Sinon, cliquez sur <i>Parcourir…</i> et sélectionnez <code>VotreClinique.lic</code>.</li>
      <li><b>Dossier d'installation</b> : gardez la valeur proposée.</li>
      <li><b>Compte principal</b> : choisissez votre <b>nom d'utilisateur</b> et un <b>mot de passe</b> (10 caractères minimum, lettres + chiffres + un symbole). Notez-les précieusement : ils seront demandés à chaque ouverture.</li>
      <li><b>Options</b> : raccourci Bureau, accès depuis les autres PC de la clinique (optionnel), lancement automatique.</li>
    </ul>
  </li>
  <li>À la fin, l'application démarre : une <b>icône en forme de dent</b> apparaît à côté de l'horloge, puis la fenêtre s'ouvre.</li>
  <li>Connectez-vous avec le compte créé à l'étape 3.</li>
</ol>
<div class="tip">Votre <b>identifiant d'installation</b> est affiché à la fin de l'installation. Communiquez-le à votre revendeur s'il n'a pas encore généré votre fichier de licence. Il reste consultable dans <b>Paramètres → À propos</b>.</div>

<h2>3. Installation — ZIP (alternative)</h2>
<ol>
  <li>Clic droit sur le ZIP → <b>Extraire tout</b> dans un dossier (par exemple <code>C:\\Clinique\\Dental care software</code>). <b>Extrayez la totalité du fichier.</b></li>
  <li>Ouvrez le dossier extrait, puis le dossier <code>scripts</code>.</li>
  <li>Double-cliquez sur <b>install.bat</b>.</li>
  <li>Répondez aux questions : <i>Première installation ?</i> → <b>O</b> ; nom du dentiste ; nom d'utilisateur ; <b>mot de passe</b>.</li>
  <li>Les raccourcis sont créés automatiquement ; l'application se lance.</li>
</ol>
<div class="note">Relancer <code>install.bat</code> est sans danger : en choisissant <b>N</b> (mise à jour), les données sont conservées.</div>

<h2>4. Utilisation quotidienne</h2>
<ul>
  <li><b>Lancer</b> : double-cliquez sur le raccourci <b>HKN Dentaire</b> (Bureau ou Menu Démarrer). L'icône dent apparaît à côté de l'horloge pendant le démarrage, puis la fenêtre s'ouvre.</li>
  <li><b>Arrêter</b> : clic droit sur l'icône dent → <b>Arrêter tout et quitter</b> (arrête proprement la base de données).</li>
  <li><b>Réseau local</b> : si l'option a été activée, les autres postes accèdent à l'application via <code>http://&lt;adresse-de-ce-PC&gt;:8000</code>.</li>
</ul>

<h2>5. Mise à jour du logiciel</h2>
<p>Exécutez simplement le <b>nouveau Setup.exe</b> fourni par votre revendeur : il se réinstalle au même emplacement et <b>conserve toutes vos données</b>.</p>
<p>Avec la version ZIP : extraire le nouveau ZIP puis relancer <code>install.bat</code> en choisissant <b>N</b> (mise à jour).</p>
<h2>6. Mot de passe oublié</h2>
<p>Lancez <code>scripts\\reset_password.bat</code> (dans le dossier d'installation), saisissez un nouveau mot de passe et confirmez. Les données patients ne sont pas modifiées.</p>

<h2>7. Sauvegardes</h2>
<p>Menu <b>Paramètres → Sauvegardes</b> de l'application : créez une sauvegarde à tout moment. Il est recommandé de faire une sauvegarde <b>chaque fin de journée</b> et de conserver une copie sur clé USB ou disque externe.</p>

<h2>8. Dépannage</h2>
<table>
  <tr><th>Problème</th><th>Solution</th></tr>
  <tr><td>Message SmartScreen / antivirus à l'installation</td><td><i>Informations complémentaires → Exécuter quand même</i> (voir §2)</td></tr>
  <tr><td><i>Le port 8000 est utilisé par une autre application</i></td><td>Fermez l'autre application ; sinon redémarrez le PC et relancez</td></tr>
  <tr><td><i>runtime absent / incomplet</i> (version ZIP)</td><td>Le ZIP n'a pas été extrait entièrement — ré-extrayez tout</td></tr>
  <tr><td>L'application ne s'ouvre pas</td><td>Double-cliquez sur l'icône dent à côté de l'horloge ; si besoin utilisez <i>Console de diagnostic</i></td></tr>
  <tr><td>Mot de passe oublié / à changer</td><td><code>scripts\\reset_password.bat</code></td></tr>
  <tr><td>Licence expirée ou absente</td><td>Page <b>Licence</b> de l'application : importez le nouveau fichier <code>.lic</code></td></tr>
</table>

<h2>9. Assistance</h2>
<p>Contactez votre revendeur (HKN) en joignant :</p>
<ol>
  <li>Une capture d'écran du message d'erreur ;</li>
  <li>Votre <b>identifiant d'installation</b> (visible dans <b>Paramètres → À propos</b>).</li>
</ol>

<footer>HKN Dentaire v1.0.0 — Guide d'installation et d'utilisation — document fourni avec le logiciel.</footer>
</body>
</html>
""".replace("__ICON__", ICON_B64)

html_path = TMP / "guide.html"
html_path.write_text(HTML, encoding="utf-8")

pdf_path = ROOT / "HKN_Dentaire_Installation_Guide.pdf"
chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
cmd = [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
       "--print-to-pdf=" + str(pdf_path), str(html_path)]
proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120)
if not pdf_path.exists():
    print(proc.stdout)
    print(proc.stderr)
    raise SystemExit("PDF generation failed")
print("PDF:", pdf_path, pdf_path.stat().st_size, "bytes")
