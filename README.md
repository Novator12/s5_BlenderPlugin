**Siedler 5 DFF-Plugin für Blender 5.0.1**

Ein Plugin für Blender 5.0.1 zur Bearbeitung und Konvertierung von Siedler 5 (The Settlers: Heritage of Kings)-Gebäudemodellen über ein JSON/DFF-Zwischenformat.

Operiert mit dem JSON/DFF-Konverter von [@mcb5637](https://github.com/mcb5637/S5Converter)

✅ Funktionsumfang

🔽 Import

    Import von Gebäudedaten aus JSON:

        HAnim

        UserData

        Geometries

        Atomics

        Animations

🛠 Bearbeitung

    Bone-System erweitern:

        Hinzufügen von Building Texture Bones und Decal Bones

    Physikalische Daten:

        Hinzufügen von Bounding-Sphere (Sphere) für Ingame-Kollision und Selektion

        Automatische Generierung von Bounding Spheres, basierend auf der Meshgröße

    Partikeleffekte:

        Hinzufügen vordefinierter Partikeleffekte zu Gebäuden

    Geometriekonfiguration pro Mesh:

        Materialzuweisung

        UV-Transformation

        Dual-Texturierung

        Konfiguration von Ambient-, Specular- und Diffuse-Parametern

        Schnee-Texturen

        Alpha-Texturen

📤 Export

    !Beachten!: Meshes müssen folgendes Namensschema haben: Mesh1, Mesh2,...,Mesh11,Mesh12,...

    Export in JSON und DFF-Format

    Automatische Generierung von HAnimPLG (Nodes & Parents) beim Export

    Animationen: Namensgebung bei Import nach Siedler 5 Standard notwendig: "pb_foundry2_cannon1_600.anm" 
    -> RootNode wird aus dem Namen ausgelesen (auch beim Export beachten für späteren Neuimport)

🧪 Geplant

    Generierung von BinMesh-Daten beim Export

⚙ Kompatibilität

    Blender-Version: 5.0.1

    Python: 3.11.13

    Kompatibel mit externen Tools zur DFF-Konvertierung für Siedler 5

📝 Lizenz & Hinweise

    Mathematische Berechnung des Modelimports (.dff) basiert auf Kimichuras Siedler 5 Plugin (shokimpexp_rigid.py [Quelle: Siedler MP Server, Discord]), sowie Elementen seiner Codestruktur

Dieses Plugin befindet sich in Entwicklung. Es wird empfohlen, regelmäßig Backups der Blender-Dateien zu erstellen.
Für Fragen, Vorschläge oder Bugs: Issue auf GitHub erstellen.


⚙️ Neue Funktionen:

User-Data für Decal und Building Bones anlegen:
<img width="1776" height="1159" alt="grafik" src="https://github.com/user-attachments/assets/96b1f2ad-d947-4fd2-a1d1-464f4a781c87" />

Generierung von Bounding Spheres:
<img width="1745" height="1181" alt="grafik" src="https://github.com/user-attachments/assets/4ee488f4-a9fa-4619-bb9a-414fb2fb0e7f" />

Erkennung und additives Hinzufügen von Particle Effekten:
<img width="1564" height="1129" alt="grafik" src="https://github.com/user-attachments/assets/9cf9b1ef-50a4-4dca-b601-d925c2fb7908" />

Erkennen und anlegen von Materialdaten:
<img width="1800" height="1183" alt="grafik" src="https://github.com/user-attachments/assets/1b913b7f-a9bd-4da6-873f-aa8e8eaf203e" />

Resetten der gesamten Szene:
<img width="1728" height="1154" alt="grafik" src="https://github.com/user-attachments/assets/0fc6e5c9-a10f-41cf-801e-7b4272ea9b44" />



