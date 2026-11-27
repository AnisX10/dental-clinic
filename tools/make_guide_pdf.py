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
  <div class="cover-sub">Guide d'installation et d'utilisation<br>Version 1.0.0 &mdash; Novembre 2026</div>
</div>

<h2>1. Ce que vous recevez</h2>
<table>
  <tr><th>Livraison</th><th>Contenu</th></tr>
  <tr><td><code>HKN Dentaire Setup.exe</code></td><td>Programme d'installation en un seul fichier (recommandé)</td></tr>
  <tr><td><code>HKN Dentaire.zip</code></td><td>Version portable (alternative)</td></tr>
  <tr><td><b>Clé de licence</b></td><td>Une ligne de texte (elle commence par <code>HKN1.</code>), fournie par votre revendeur — à coller pendant l'installation ou à la première ouverture</td></tr>
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
      <li><b>Clé de licence</b> : collez la clé reçue de votre revendeur (une seule ligne). Facultatif ici — sans clé, l'écran d'activation s'affichera à la première ouverture et vous pourrez la coller alors.</li>
      <li><b>Dossier d'installation</b> : gardez la valeur proposée. Le chemin ne doit contenir <b>ni accents ni lettres arabes</b> : si votre nom d'utilisateur Windows en contient, l'assistant propose automatiquement <code>C:\\HKN Dentaire</code>. Évitez OneDrive, les lecteurs réseau et les clés USB.</li>
      <li><b>Compte principal</b> (première installation) : saisissez le nom complet du dentiste, puis choisissez votre <b>nom d'utilisateur</b> et un <b>mot de passe</b> (10 caractères minimum, lettres + chiffres + un symbole). Notez-les précieusement : ils seront demandés à chaque ouverture. Une mise à jour conserve les comptes existants.</li>
      <li><b>Options</b> : raccourci Bureau, <b>accès depuis les autres PC de la clinique</b> (uniquement si d'autres postes doivent se connecter), <b>Démarrer HKN Dentaire avec Windows</b> (recommandé sur le PC principal : application et sauvegardes automatiques actives dès l'ouverture de session, sans fenêtre).</li>
    </ul>
  </li>
  <li>À la fin, l'application démarre : une <b>icône en forme de dent</b> apparaît à côté de l'horloge, puis la fenêtre s'ouvre.</li>
  <li>Connectez-vous avec le compte créé à l'étape 3.</li>
</ol>
<div class="tip">Si l'écran <b>Licence</b> s'affiche à l'ouverture : collez la clé dans la zone prévue et cliquez <b>Activer</b>.</div>

<h2>3. Installation — ZIP (alternative)</h2>
<ol>
  <li>Clic droit sur le ZIP → <b>Extraire tout</b> dans un dossier sans accents (par exemple <code>C:\\Clinique</code>). <b>Extrayez la totalité du fichier.</b></li>
  <li>Ouvrez le dossier extrait, puis le dossier <code>scripts</code>.</li>
  <li>Double-cliquez sur <b>install.bat</b>.</li>
  <li>Répondez aux questions : <i>Première installation ?</i> → <b>O</b> ; nom du dentiste ; nom d'utilisateur ; <i>accès réseau local ?</i> (<b>O</b> seulement si d'autres PC doivent se connecter) ; <b>clé de licence</b> (collez-la, ou Entrée pour ignorer) ; <b>mot de passe</b>, saisi deux fois.</li>
  <li>Les raccourcis sont créés automatiquement ; l'application se lance.</li>
</ol>
<div class="note">Relancer <code>install.bat</code> est sans danger : en choisissant <b>N</b> (mise à jour), les données sont conservées.</div>

<h2>4. Utilisation quotidienne</h2>
<ul>
  <li><b>Lancer</b> : double-cliquez sur le raccourci <b>HKN Dentaire</b> (Bureau ou Menu Démarrer). L'icône dent apparaît à côté de l'horloge pendant le démarrage, puis la fenêtre s'ouvre.</li>
  <li><b>Arrêter</b> : clic droit sur l'icône dent → <b>Arrêter tout et quitter</b> (arrête proprement la base de données).</li>
  <li><b>Réseau local</b> : si l'option a été activée, les autres postes accèdent à l'application via <code>http://&lt;adresse-de-ce-PC&gt;:8000</code>. Sans cette option, seul ce PC peut ouvrir l'application.</li>
  <li><b>Redémarrage automatique</b> : si l'application s'arrête de façon inattendue, l'icône dent la relance d'elle-même en quelques secondes.</li>
</ul>

<h2>5. Mise à jour du logiciel</h2>
<p>Exécutez simplement le <b>nouveau Setup.exe</b> fourni par votre revendeur : il se réinstalle au même emplacement et <b>conserve toutes vos données</b>. Une sauvegarde complète est faite automatiquement avant toute modification de la base de données.</p>
<p>Avec la version ZIP : extraire le nouveau ZIP puis relancer <code>install.bat</code> en choisissant <b>N</b> (mise à jour).</p>
<h2>6. Mot de passe oublié</h2>
<p>Lancez <code>scripts\\reset_password.bat</code> (dans le dossier d'installation), saisissez un nouveau mot de passe et confirmez. Les données patients ne sont pas modifiées.</p>

<h2>7. Sauvegardes</h2>
<ul>
  <li><b>Automatiques</b> : une sauvegarde par jour (13 h par défaut, modifiable dans <b>Paramètres → Sauvegardes</b>). Si le PC était éteint à l'heure prévue, elle est faite dans les minutes qui suivent le prochain démarrage. Les radiographies et documents joints sont sauvegardés avec la base.</li>
  <li><b>Vérification</b> : chaque semaine, la dernière sauvegarde est restaurée dans une base de test pour vérifier qu'elle est exploitable.</li>
  <li><b>Alertes</b> : l'écran d'accueil signale une sauvegarde en retard ou en échec, et un disque presque plein.</li>
  <li><b>Manuelle</b> : <b>Paramètres → Sauvegardes → Sauvegarder maintenant</b>.</li>
  <li><b>Copie externe</b> : les sauvegardes sont dans <code>data\\backups</code> (dossier d'installation). Copiez ce dossier régulièrement sur une clé USB ou un disque externe.</li>
  <li><b>Restauration</b> (avec votre revendeur) : les données actuelles sont d'abord sauvegardées et conservées ; en cas d'échec, rien n'est modifié.</li>
</ul>

<h2>8. Dépannage</h2>
<table>
  <tr><th>Problème</th><th>Solution</th></tr>
  <tr><td>Message SmartScreen / antivirus à l'installation</td><td><i>Informations complémentaires → Exécuter quand même</i> (voir §2)</td></tr>
  <tr><td><i>Le port 8000 est utilisé par une autre application</i></td><td>Fermez l'autre application ; sinon redémarrez le PC et relancez</td></tr>
  <tr><td><i>runtime absent / incomplet</i> (version ZIP)</td><td>Le ZIP n'a pas été extrait entièrement — ré-extrayez tout</td></tr>
  <tr><td>L'application ne s'ouvre pas</td><td>Double-cliquez sur l'icône dent à côté de l'horloge ; si besoin utilisez <i>Console de diagnostic</i></td></tr>
  <tr><td>Mot de passe oublié / à changer</td><td><code>scripts\\reset_password.bat</code></td></tr>
  <tr><td>Écran Licence demandé à l'ouverture</td><td>Collez la clé de licence reçue de votre revendeur (commence par <code>HKN1.</code>) puis cliquez <b>Activer</b></td></tr>
  <tr><td>Bandeau « Licence inactive : consultation et sauvegarde uniquement »</td><td>Vos données restent consultables et sauvegardables ; activez la licence (<b>Paramètres → Licence</b>) pour pouvoir les modifier</td></tr>
  <tr><td>« Le dossier d'installation contient des caractères non pris en charge »</td><td>Réinstallez dans <code>C:\\HKN Dentaire</code> (voir §2)</td></tr>
  <tr><td>Clé refusée (« illisible » ou « signature »)</td><td>Vérifiez que la clé est collée entière, sur une seule ligne ; sinon demandez une nouvelle clé au revendeur</td></tr>
</table>

<h2>9. Assistance</h2>
<p>Contactez votre revendeur (HKN) en joignant :</p>
<ol>
  <li>Une capture d'écran du message d'erreur ;</li>
  <li>Votre <b>identifiant d'installation</b> (visible sur l'écran <b>Licence</b> ou dans <b>Paramètres → Licence</b>) ;</li>
  <li>Les journaux : clic droit sur l'icône dent → <b>Ouvrir les journaux</b>, puis joignez le fichier <code>server.log</code>.</li>
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
