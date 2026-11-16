# Dentilo by Tasshil — Guide d'installation & d'utilisation
### Guide pas à pas pour les cabinets dentaires

Bienvenue dans **Dentilo** ! Ce guide est écrit pour les chirurgiens-dentistes et les assistant(e)s, sans jargon technique.

> [!NOTE]
> **Aucun prérequis technique :** pas besoin d'installer Python ni une base de données. Tout le moteur est embarqué dans le dossier de l'application.

---

## 📋 Ce qu'il vous faut

L'application fonctionne **en local sur l'ordinateur du cabinet**, sans connexion Internet.

1. **Un PC sous Windows** (Windows 10 ou Windows 11).
2. **Le dossier de l'application** (archive `.zip` remise par Tasshil).
3. **Votre fichier de licence** (`.lic`), remis par Tasshil après l'installation (voir étape 4).

---

## 🚀 Installation

### Étape 1 : Décompresser l'archive
1. Créez un dossier sur le disque principal (ex : `C:\Dentilo`).
2. Extrayez **tout** le contenu de l'archive dans ce dossier.
   *(Vous y trouverez `install.bat`, `start.bat`, `stop.bat` et le dossier `runtime`.)*

### Étape 2 : Lancer l'assistant d'installation
1. Double-cliquez sur 👉 **`install.bat`**.
2. Répondez aux questions :
   - **Nom du médecin** *(ex : Dr. Benali Amine)*
   - **Identifiant de connexion** *(ex : dentiste)*
   - **Mot de passe** : choisissez-le vous-même. La saisie est masquée et demandée deux fois.
     Il doit contenir **au moins 10 caractères, avec des lettres, des chiffres et un symbole**.
     Il n'existe **aucun mot de passe par défaut**.
3. Le raccourci **« Dentilo »** est créé sur le Bureau.

### Étape 3 : Premier lancement
Double-cliquez sur le raccourci **Dentilo**. L'application s'ouvre dans une fenêtre dédiée.

> [!IMPORTANT]
> Si l'application est lancée avec `start.bat` **sans** avoir passé l'étape 2, elle crée le compte `dentiste` avec un **mot de passe provisoire aléatoire**, écrit dans le fichier `data\PREMIER-ACCES.txt`. Ce mot de passe doit être changé dès la première connexion ; supprimez ensuite ce fichier.

### Étape 4 : Activer la licence
1. Au premier lancement, l'écran **« Licence inactive »** affiche le **numéro d'installation** de ce poste.
2. Transmettez ce numéro à Tasshil.
3. Vous recevez un fichier `.lic` valable **uniquement pour cette installation**. Cliquez sur **« Installer la licence »** et choisissez ce fichier.

> [!NOTE]
> Une licence est liée à une seule installation. Si vous réinstallez sur un autre PC, demandez une nouvelle licence.

---

## 🖥️ Utilisation quotidienne

### Ouvrir l'application
- Double-cliquez sur le raccourci **Dentilo** du Bureau.

### Changer son mot de passe
- Cliquez sur votre nom en haut à droite, puis choisissez un nouveau mot de passe.
- Chaque personne du cabinet (dentiste, réception) doit avoir **son propre compte**.

### Connecter le poste de réception
1. Les deux ordinateurs doivent être sur le même réseau local (box du cabinet ou câble).
2. Sur le PC principal, ouvrez l'invite de commandes et tapez `ipconfig` pour noter son adresse IP locale (ex : `192.168.1.15`).
3. Sur le PC de réception, ouvrez Chrome ou Edge à l'adresse `http://192.168.1.15:8000`.
4. La réception se connecte avec **son propre compte**.

> [!WARNING]
> La connexion entre les deux postes n'est pas chiffrée (HTTP). Utilisez uniquement le réseau privé du cabinet, protégé par un mot de passe Wi-Fi, et **n'exposez jamais l'application sur Internet**.

### Fermer l'application
- Fermez la fenêtre en fin de journée.
- Pour arrêter complètement le serveur, double-cliquez sur 👉 **`stop.bat`**.

---

## 💾 Sauvegardes

### Ce qui est sauvegardé
- Chaque soir à **20h00** (modifiable dans **Paramètres → Sauvegarde**), une sauvegarde de la base de données (patients, actes, odontogrammes, paiements, documents) est écrite dans `data\backups\`.
- Bouton **« Sauvegarder maintenant »** dans **Paramètres → Sauvegarde** pour une sauvegarde immédiate.

> [!WARNING]
> **Limites actuelles, à connaître :**
> - Les **pièces jointes** des patients (radios, photos, fichiers importés, dossier `data\attachments\`) ne sont **pas** incluses dans la sauvegarde automatique. Copiez ce dossier vous-même.
> - Les sauvegardes **ne sont pas chiffrées**. Conservez la clé USB ou le disque de sauvegarde en lieu sûr.

### Conseil
Copiez régulièrement les dossiers `data\backups` **et** `data\attachments` sur une clé USB ou un disque externe rangé hors du cabinet.

---

## 🖨️ Impression des ordonnances et devis

1. Renseignez d'abord le **nom du cabinet**, le **médecin**, l'**adresse** et le **téléphone** dans **Paramètres** : ils forment l'en-tête des documents imprimés.
2. Cliquez sur **Imprimer**, puis dans la fenêtre d'impression :
   - **Marges :** « Par défaut ».
   - **Options :** cochez **« Graphiques d'arrière-plan »**.
