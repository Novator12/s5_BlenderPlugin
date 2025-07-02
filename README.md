Siedler 5 DFF-Plugin für Blender 2.79

Ein Plugin für Blender 2.79 zur Bearbeitung und Konvertierung von Siedler 5 (The Settlers: Heritage of Kings)-Gebäudemodellen über ein JSON/DFF-Zwischenformat.

Operiert mit dem JSON/DFF-Konverter von [@mcb5637](https://github.com/mcb5637/S5Converter)

✅ Funktionsumfang

🔽 Import

    Import von Gebäudedaten aus JSON:

        HAnim

        UserData

        Geometries

        Atomics

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

🧪 Geplant

    Generierung von BinMesh-Daten beim Export

    Import und Export von Animationen für Gebäude

⚙ Kompatibilität

    Blender-Version: 2.79

    Python: 3.5.3

    Kompatibel mit externen Tools zur DFF-Konvertierung für Siedler 5

📝 Lizenz & Hinweise

Dieses Plugin befindet sich in Entwicklung. Es wird empfohlen, regelmäßig Backups der Blender-Dateien zu erstellen.
Für Fragen, Vorschläge oder Bugs: Issue auf GitHub erstellen.


⚙️ Neue Funktionen:

User-Data für Decal und Building Bones anlegen:
![grafik](https://github.com/user-attachments/assets/681dc428-140c-4f79-b9ef-b8c26a35450d)

Generierung von Bounding Spheres:
![grafik](https://github.com/user-attachments/assets/ca1d2f9d-0645-42ce-8d33-fa4f617de3e3)

Erkennung und additives Hinzufügen von Particle Effekten:
![grafik](https://github.com/user-attachments/assets/d060aa6d-183b-44d9-8594-d2ad702213b5)

Erkennen und anlegen von Materialdaten:
![grafik](https://github.com/user-attachments/assets/915752d4-ba0f-4853-9f31-a681fe088b48)

Resetten der gesamten Szene:
![grafik](https://github.com/user-attachments/assets/42643b07-7543-40b8-a68d-86725adcc93f)


