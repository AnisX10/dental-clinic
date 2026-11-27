# HKN Dentaire — Guide d'installation et d'utilisation

Version 1.0.0 — Novembre 2026

---

## 1. Ce que vous recevez

| Livraison | Contenu |
|---|---|
| `HKN Dentaire Setup.exe` | Programme d'installation en un seul fichier (recommandé) |
| `HKN Dentaire.zip` | Version portable (alternative) |
| **Clé de licence** | Une ligne de texte (elle commence par `HKN1.`), fournie par votre revendeur — à coller pendant l'installation ou à la première ouverture |

**Aucun accès à Internet n'est requis.** Tout est intégré : application, base de données, environnements d'exécution.

---

## 2. Installation — Setup.exe (recommandé)

1. Double-cliquez sur **HKN Dentaire Setup.exe**.
   - Si Windows affiche *« Windows a protégé votre ordinateur »* (SmartScreen) : cliquez sur **Informations complémentaires** puis **Exécuter quand même**. Ce message apparaît car le programme n'est pas signé par une grande société ; il provient de votre revendeur.
   - Si votre antivirus affiche un avertissement, vérifiez que le fichier provient bien de votre revendeur, puis autorisez-le.
2. Suivez l'assistant :
   - **Clé de licence** : collez la clé reçue de votre revendeur (une seule ligne). Cette étape est facultative — sans clé, l'écran d'activation s'affichera à la première ouverture et vous pourrez la coller alors.
   - **Dossier d'installation** : gardez la valeur proposée. Le chemin ne doit contenir **ni accents ni lettres arabes** (limite de la base de données) : si votre nom d'utilisateur Windows en contient, l'assistant propose automatiquement `C:\HKN Dentaire`. Évitez les dossiers synchronisés OneDrive, les lecteurs réseau et les clés USB.
   - **Compte principal** (première installation) : saisissez le nom complet du dentiste, puis choisissez votre **nom d'utilisateur** et un **mot de passe** (10 caractères minimum, avec lettres, chiffres et un symbole). Notez-les précieusement : ils seront demandés à chaque ouverture. Une mise à jour conserve les comptes existants.
   - **Options** : raccourci Bureau, **accès depuis les autres PC de la clinique** (à cocher uniquement si d'autres postes doivent se connecter), **Démarrer HKN Dentaire avec Windows** (recommandé sur le PC principal : l'application et les sauvegardes automatiques tournent dès l'ouverture de session, sans fenêtre).
3. À la fin, l'application démarre : une **icône en forme de dent** apparaît à côté de l'horloge, puis la fenêtre de l'application s'ouvre.
4. Connectez-vous avec le compte créé à l'étape 3.

> Si l'écran **Licence** s'affiche à l'ouverture : collez la clé dans la zone prévue et cliquez **Activer**.

---

## 3. Installation — ZIP (alternative)

1. Clic droit sur le ZIP → **Extraire tout** dans un dossier sans accents (par exemple `C:\Clinique`). **Extrayez la totalité du fichier.**
2. Ouvrez le dossier extrait, puis le dossier `scripts`.
3. Double-cliquez sur **install.bat**.
4. Répondez aux questions :
   - *Première installation ?* → **O**
   - Nom du dentiste, nom d'utilisateur.
   - *Accès réseau local ?* → **O** seulement si d'autres PC doivent se connecter (sinon **N**).
   - *Clé de licence* → **collez la clé reçue de votre revendeur** (ou appuyez sur Entrée pour ignorer cette étape).
   - **Mot de passe**, saisi deux fois (10 caractères minimum : lettres, chiffres et un symbole).
5. Les raccourcis sont créés automatiquement ; l'application se lance.

En cas de difficulté, tout est réitérable : relancer `install.bat` est sans danger (les données sont conservées si vous choisissez **N** = mise à jour).

---

## 4. Utilisation quotidienne

- **Lancer** : double-cliquez sur le raccourci **HKN Dentaire** (Bureau ou Menu Démarrer). L'icône dent apparaît à côté de l'horloge pendant le démarrage, puis la fenêtre s'ouvre. Si vous la fermez sans le vouloir, double-cliquez à nouveau sur l'icône tray.
- **Arrêter** : clic droit sur l'icône dent → **Arrêter tout et quitter** (arrête proprement la base de données).
- **Réseau local** : si l'option a été activée, les autres postes de la clinique accèdent à l'application via `http://<adresse-de-ce-PC>:8000`. Sans cette option, seul ce PC peut ouvrir l'application.
- **Redémarrage automatique** : si l'application s'arrête de façon inattendue, l'icône dent la relance d'elle-même en quelques secondes.

---

## 5. Mise à jour du logiciel

Exécutez simplement le **nouveau Setup.exe** fourni par votre revendeur : il se réinstalle au même emplacement et **conserve toutes vos données**. Une sauvegarde complète est faite automatiquement avant toute modification de la base de données.

Avec la version ZIP : extraire le nouveau ZIP puis relancer `install.bat` en choisissant **N** (mise à jour). Les données sont conservées.

---

## 6. Mot de passe oublié

Lancez `scripts\reset_password.bat` (dans le dossier d'installation), saisissez un nouveau mot de passe et confirmez. Les données patients ne sont pas modifiées.

---

## 7. Sauvegardes

- **Automatiques** : une sauvegarde par jour (13 h par défaut, modifiable dans **Paramètres → Sauvegardes**). Si le PC était éteint à l'heure prévue, elle est faite dans les minutes qui suivent le prochain démarrage. Les radiographies et documents joints sont sauvegardés avec la base.
- **Vérification** : chaque semaine, l'application restaure la dernière sauvegarde dans une base de test pour vérifier qu'elle est exploitable.
- **Alertes** : l'écran d'accueil signale une sauvegarde en retard ou en échec, et un disque presque plein.
- **Manuelle** : **Paramètres → Sauvegardes → Sauvegarder maintenant**.
- **Copie externe** : les sauvegardes se trouvent dans `dataackups` (dans le dossier d'installation). Copiez ce dossier régulièrement sur une clé USB ou un disque externe.
- **Restauration** (avec votre revendeur) : fermez l'application, puis `runtime\python.exe backendpp\cli.py restore --backup <fichier.dump>`. Les données actuelles sont d'abord sauvegardées et conservées ; en cas d'échec, rien n'est modifié.

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
| Écran Licence demandé à l'ouverture | Collez la clé de licence reçue de votre revendeur (commence par `HKN1.`) puis cliquez **Activer** |
| Bandeau « Licence inactive : consultation et sauvegarde uniquement » | Vos données restent consultables et sauvegardables ; activez la licence (**Paramètres → Licence**) pour pouvoir les modifier |
| « Le dossier d'installation contient des caractères non pris en charge » | Réinstallez dans `C:\HKN Dentaire` (voir §2) |
| Clé refusée (« illisible » ou « signature ») | Vérifiez que la clé est collée **entière**, sur une seule ligne. Si le revendeur doit vous en envoyer une nouvelle, elle doit être transmise comme fichier texte ou message à copier intégralement |

---

## 9. Assistance

Contactez votre revendeur (HKN) en joignant :
1. Une capture d'écran du message d'erreur ;
2. Votre **identifiant d'installation** (visible sur l'écran **Licence** ou dans **Paramètres → Licence**) ;
3. Les journaux : clic droit sur l'icône dent → **Ouvrir les journaux**, puis joignez le fichier `server.log`.
