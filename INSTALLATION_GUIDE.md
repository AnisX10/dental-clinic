# HKN Dentaire — Guide d'Installation & Utilisation
### Guide complet pas à pas pour les cabinets dentaires

Bienvenue dans **HKN Dentaire** ! Ce guide est conçu en langage clair et simple pour les chirurgiens-dentistes, gestionnaires de cabinets et assistant(e)s. 

> [!NOTE]
> **Zero prérequis technique :** Vous n'avez PAS besoin d'installer Python, ni de base de données, ni de configurer des variables d'environnement. Tout le moteur est 100% autonome et pré-embarqué dans l'application.

---

## 📋 Prérequis matériels

L'application fonctionne **100% en local sur votre ordinateur** sans connexion Internet requise.

Vous avez uniquement besoin de :
1. **Un PC sous Windows** (Windows 10 ou Windows 11).
2. **Le package logiciel** (`clinicfinal2026.zip`).

---

## 🚀 Installation Express en 1 Clic

### Étape 1 : Décompresser l'archive
1. Créez un dossier sur votre disque principal (ex : `C:\clinic` ou sur votre Bureau).
2. Extrayez l'intégralité du fichier `clinicfinal2026.zip` dans ce dossier.
   *(Vous y trouverez les fichiers `start.bat`, `install.bat`, `stop.bat` et le dossier `runtime`).*

---

### Étape 2 : Lancer l'assistant d'installation
1. Double-cliquez sur :
   👉 **`install.bat`**
2. Le programme configure le cabinet en quelques secondes :
   - Détection automatique de l'environnement portable embarqué.
   - Saisie rapide des coordonnées du praticien (ou appuyez sur Entrée pour les valeurs par défaut) :
     - **Nom du médecin** *(ex : Dr. Benali Amine)*
     - **Identifiant de connexion** *(ex : dentiste)*
     - **Mot de passe** *(ex : Cabinet2026!)*
3. Le raccourci **"HKN Dentaire"** est automatiquement créé sur votre Bureau Windows !
4. L'application se lance immédiatement prête à l'emploi.

> [!TIP]
> **Démarrage direct sans installation :** Vous pouvez également double-cliquer directement sur **`start.bat`** ! L'application initialise automatiquement la base de données, active la licence intégrée et s'ouvre dans votre navigateur sans aucune question. Identifiant par défaut : `dentiste` / Mot de passe : `Cabinet2026!`.

---

## 🖥️ Utilisation quotidienne

### Comment ouvrir l'application
- Double-cliquez simplement sur le raccourci **HKN Dentaire** sur votre Bureau Windows.
- L'application s'ouvre dans une fenêtre d'application dédiée et épurée (style natif sans barre d'onglets).

### Connecter un second ordinateur (Poste Réception / Secrétariat)
Si votre cabinet dispose d'un poste d'accueil ou d'une seconde salle de soins :
1. Connectez les deux ordinateurs au même réseau local (box Wi-Fi du cabinet ou câble réseau).
2. Sur le PC principal, ouvrez l'invite de commande et tapez `ipconfig` pour noter son adresse IP locale (ex : `192.168.1.15`).
3. Sur le PC de réception, ouvrez Chrome ou Edge et rendez-vous sur :
   ```
   http://192.168.1.15:8000
   ```
4. L'assistant(e) peut se connecter avec son propre compte !

### Comment fermer l'application
- Vous pouvez simplement fermer la fenêtre à la fin de votre journée.
- Pour stopper complètement le serveur d'arrière-plan, double-cliquez sur :
  👉 **`stop.bat`**

---

## 💾 Sauvegardes & Sécurité des données

Les dossiers médicaux de vos patients sont protégés automatiquement :

### Sauvegarde automatique quotidienne
- Chaque soir à **20h00**, le système effectue une sauvegarde complète et chiffrée de tous les patients, actes, odontogrammes et paiements dans :
  `data\backups\`
- Vous pouvez modifier l'heure de sauvegarde à tout moment dans **Paramètres → Sauvegarde**.

### Sauvegarde manuelle instantanée
1. Dans le menu de l'application, cliquez sur **Paramètres**.
2. Dans la section **Sauvegarde**, cliquez sur **"Sauvegarder maintenant"**.

> [!TIP]
> **Conseil sécurité :** Branchez une clé USB sur votre ordinateur et copiez le dossier `data\backups` dessus régulièrement. En cas de panne matérielle de votre PC, l'intégralité de votre cabinet est récupérable en 5 minutes.

---

## 🖨️ Impression des ordonnances et devis

1. Lors du clic sur **Imprimer** :
2. Dans la boîte de dialogue d'impression de votre navigateur :
   - **Marges :** Sélectionnez **"Par défaut"**.
   - **Options :** Cochez impérativement la case **"Graphiques d'arrière-plan"**.
3. Vos ordonnances sortiront avec le logo du cabinet, le filigrane et les bordures parfaitement alignés au format A4.
