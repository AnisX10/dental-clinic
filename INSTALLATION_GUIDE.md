# HKN Dentaire — Guide d'installation et d'utilisation

Version 1.0.0 — Octobre 2026

---

## 1. Ce que vous recevez

| Livraison | Contenu |
|---|---|
| `HKN Dentaire Setup.exe` | Programme d'installation en un seul fichier (recommandé) |
| `HKN Dentaire.zip` | Version portable (alternative) |
| `VotreClinique.lic` | Fichier de licence de votre clinique (fourni séparément par votre revendeur) |

**Aucun accès à Internet n'est requis.** Tout est intégré : application, base de données, environnements d'exécution.

---

## 2. Installation — Setup.exe (recommandé)

1. Double-cliquez sur **HKN Dentaire Setup.exe**.
   - Si Windows affiche *« Windows a protégé votre ordinateur »* (SmartScreen) : cliquez sur **Informations complémentaires** puis **Exécuter quand même**. Ce message apparaît car le programme n'est pas signé par une grande société ; il provient de votre revendeur.
   - Si votre antivirus affiche un avertissement, vérifiez que le fichier provient bien de votre revendeur, puis autorisez-le.
2. Suivez l'assistant :
   - **Licence** : le programme détecte automatiquement un fichier `.lic` situé à côté du Setup. Sinon, cliquez sur *Parcourir…* et sélectionnez `VotreClinique.lic`.
   - **Dossier d'installation** : gardez la valeur proposée (`%LOCALAPPDATA%\Programs\HKN Dentaire`).
   - **Compte principal** : choisissez votre **nom d'utilisateur** et un **mot de passe** (10 caractères minimum, avec lettres, chiffres et un symbole). Notez-les précieusement : ils seront demandés à chaque ouverture.
   - **Options** : raccourci Bureau, accès depuis les autres PC de la clinique (optionnel), lancement automatique.
3. À la fin, l'application démarre : une **icône en forme de dent** apparaît à côté de l'horloge, puis la fenêtre de l'application s'ouvre.
4. Connectez-vous avec le compte créé à l'étape 3.

> Votre identifiant d'installation (nécessaire pour activer la licence) est affiché à la fin de l'installation. Le copier et l'envoyer à votre revendeur s'il n'a pas encore généré votre fichier de licence.

---

## 3. Installation — ZIP (alternative)

1. Clic droit sur le ZIP → **Extraire tout** dans un dossier (par exemple `C:\Clinique\Dental care software`). **Extrayez la totalité du fichier.**
2. Ouvrez le dossier extrait, puis le dossier `scripts`.
3. Double-cliquez sur **install.bat**.
4. Répondez aux questions :
   - *Première installation ?* → **O**
   - Nom du dentiste, nom d'utilisateur, **mot de passe** (saisi deux fois dans votre tête — un seul champ ici).
5. Les raccourcis sont créés automatiquement ; l'application se lance.

En cas de difficulté, tout est réitérable : relancer `install.bat` est sans danger (les données sont conservées si vous choisissez **N** = mise à jour).

---

## 4. Utilisation quotidienne

- **Lancer** : double-cliquez sur le raccourci **HKN Dentaire** (Bureau ou Menu Démarrer). L'icône dent apparaît à côté de l'horloge pendant le démarrage, puis la fenêtre s'ouvre. Si vous la fermez sans le vouloir, double-cliquez à nouveau sur l'icône tray.
- **Arrêter** : clic droit sur l'icône dent → **Arrêter tout et quitter** (arrête proprement la base de données).
- **Réseau local** : si l'option a été activée, les autres postes de la clinique accèdent à l'application via `http://<adresse-de-ce-PC>:8000`.

---

## 5. Mise à jour du logiciel

Exécutez simplement le **nouveau Setup.exe** fourni par votre revendeur : il se réinstalle au même emplacement et **conserve toutes vos données**.

Avec la version ZIP : extraire le nouveau ZIP puis relancer `install.bat` en choisissant **N** (mise à jour). Les données sont conservées.

---

## 6. Mot de passe oublié

Lancez `scripts\reset_password.bat` (dans le dossier d'installation), saisissez un nouveau mot de passe et confirmez. Les données patients ne sont pas modifiées.

---

## 7. Sauvegardes

Menu **Paramètres → Sauvegardes** de l'application : créez une sauvegarde à tout moment. Il est recommandé de faire une sauvegarde **chaque fin de journée** et de conserver une copie sur clé USB ou disque externe.

---

## 8. Dépannage

| Problème | Solution |
|---|---|
| Message SmartScreen / antivirus à l'installation | *Informations complémentaires → Exécuter quand même* (voir §2) |
| `Le port 8000 est utilisé par une autre application` | Fermez l'autre application ; sinon redémarrez le PC et relancez |
| Erreur « runtime absent / incomplet » (version ZIP) | Le ZIP n'a pas été extrait entièrement — ré-extrayez tout |
| L'application ne s'ouvre pas | Double-cliquez sur l'icône dent à côté de l'horloge ; si besoin utilisez *Console de diagnostic* (clic droit sur l'icône) |
| Mot de passe oublié | `scripts\reset_password.bat` (§6) |
| Changer le mot de passe / le compte | `scripts\reset_password.bat` |
| Licence expirée ou absente | Page **Licence** de l'application : importez le nouveau fichier `.lic` fourni par votre revendeur |

---

## 9. Assistance

Contactez votre revendeur (HKN) en joignant :
1. Une capture d'écran du message d'erreur ;
2. Votre **identifiant d'installation** (visible dans **Paramètres → À propos**).
