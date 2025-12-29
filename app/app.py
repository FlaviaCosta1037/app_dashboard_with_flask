from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import json
import os
import uuid

app = Flask(__name__)
app.secret_key = "dev-secret-key-v2"

# =====================================================
# 🔹 DIRETÓRIOS
# =====================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =====================================================
# 🔹 HELPERS DE PROJETO
# =====================================================

def project_path(project_id):
    return os.path.join(PROJECTS_DIR, f"{project_id}.json")


def save_project(project):
    with open(project_path(project["id"]), "w", encoding="utf-8") as f:
        json.dump(project, f, indent=2, ensure_ascii=False)


def load_project(project_id):
    path = project_path(project_id)

    if not os.path.exists(path):
        raise FileNotFoundError("Projeto não encontrado")

    if os.path.getsize(path) == 0:
        raise FileNotFoundError("Arquivo do projeto está vazio")

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_all_projects():
    projects = []

    for file in os.listdir(PROJECTS_DIR):
        path = os.path.join(PROJECTS_DIR, file)

        if not path.endswith(".json"):
            continue

        if os.path.getsize(path) == 0:
            continue

        try:
            with open(path, encoding="utf-8") as f:
                projects.append(json.load(f))
        except json.JSONDecodeError:
            continue

    return projects

# =====================================================
# 🔹 LEITURA DE TABELAS
# =====================================================

def load_table(path):
    ext = os.path.splitext(path)[1].lower()

    if ext == ".csv":
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(path, sep=None, engine="python", encoding="latin1")

    if ext in [".xls", ".xlsx"]:
        return pd.read_excel(path)

    raise ValueError("Formato não suportado")


def process_dates(df, column_types):
    for col, t in column_types.items():
        if t == "date" and col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            df[f"{col}_year"] = df[col].dt.year
            df[f"{col}_month"] = df[col].dt.month
            df[f"{col}_day"] = df[col].dt.day
    return df

# =====================================================
# 🔹 HOME
# =====================================================

@app.route("/")
def home():
    projects = load_all_projects()
    session.clear()
    return render_template("home.html", projects=projects)

# =====================================================
# 🔹 CRIAR PROJETO (MODAL)
# =====================================================

@app.route("/project/create", methods=["POST"])
def create_project():
    project_id = str(uuid.uuid4())

    project = {
        "id": project_id,
        "title": request.form["title"],
        "description": request.form.get("description", ""),
        "charts": [],
        "step": "upload"
    }

    save_project(project)
    session["project_id"] = project_id

    return redirect(url_for("dashboard", project_id=project_id))

# =====================================================
# 🔹 DASHBOARD (CONTROLLER DE FLUXO)
# =====================================================

@app.route("/dashboard/<project_id>")
def dashboard(project_id):
    project = load_project(project_id)
    session["project_id"] = project_id

    step = project.get("step", "upload")

    if step == "upload":
        return redirect(url_for("upload"))

    if step == "columns":
        return redirect(url_for("define_columns"))

    # step == ready
    return render_template("dashboard.html", project=project)

# =====================================================
# 🔹 UPLOAD DO ARQUIVO (ETAPA 1)
# =====================================================

@app.route("/upload", methods=["GET", "POST"])
def upload():
    project_id = session.get("project_id")
    if not project_id:
        return redirect(url_for("home"))

    project = load_project(project_id)

    if project.get("step") != "upload":
        return redirect(url_for("dashboard", project_id=project_id))

    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return "Arquivo não enviado", 400

        filename = f"{uuid.uuid4()}_{file.filename}"
        path = os.path.join(UPLOAD_DIR, filename)
        file.save(path)

        df = load_table(path)

        project["file_path"] = path
        project["columns"] = df.columns.tolist()
        project["column_types"] = {}
        project["step"] = "columns"

        save_project(project)

        return redirect(url_for("define_columns"))

    return render_template("upload.html", project=project)

# =====================================================
# 🔹 DEFINIR TIPOS DE COLUNA (ETAPA 2)
# =====================================================

@app.route("/columns", methods=["GET", "POST"])
def define_columns():
    project_id = session.get("project_id")
    if not project_id:
        return redirect(url_for("home"))

    project = load_project(project_id)

    if project.get("step") != "columns":
        return redirect(url_for("dashboard", project_id=project_id))

    if request.method == "POST":
        project["column_types"] = {
            col: request.form.get(col)
            for col in project["columns"]
        }

        project["step"] = "ready"
        save_project(project)

        return redirect(url_for("dashboard", project_id=project_id))

    return render_template(
        "columns.html",
        columns=project["columns"],
        project=project
    )

# =====================================================
# 🔹 CRIAR NOVO GRÁFICO
# =====================================================

@app.route("/visual/new", methods=["GET", "POST"])
def new_visual():
    project_id = session.get("project_id")
    if not project_id:
        return redirect(url_for("home"))

    project = load_project(project_id)

    if project.get("step") != "ready":
        return redirect(url_for("dashboard", project_id=project_id))

    df = load_table(project["file_path"])
    df = process_dates(df, project["column_types"])

    categories, numbers = [], []

    for col, t in project["column_types"].items():
        if t == "category":
            categories.append(col)
        elif t == "number":
            numbers.append(col)
        elif t == "date":
            categories.extend([
                f"{col}_year",
                f"{col}_month",
                f"{col}_day"
            ])

    if request.method == "POST":
        chart = {
            "id": str(uuid.uuid4()),
            "type": request.form["chart_type"],
            "x": request.form["x"],
            "y": request.form["y"]
        }

        project["charts"].append(chart)
        save_project(project)

        return redirect(url_for("dashboard", project_id=project_id))

    return render_template(
        "visual_new.html",
        project=project,
        categories=categories,
        numbers=numbers
    )
@app.route("/chart/data/<chart_id>")
def chart_data(chart_id):
    project_id = session.get("project_id")
    project = load_project(project_id)

    chart = next(c for c in project["charts"] if c["id"] == chart_id)

    df = load_table(project["file_path"])
    df = process_dates(df, project["column_types"])

    grouped = df.groupby(chart["x"])[chart["y"]].sum().reset_index()

    return {
        "type": chart["type"],
        "labels": grouped[chart["x"]].astype(str).tolist(),
        "values": grouped[chart["y"]].tolist(),
        "y": chart["y"]
    }

# =====================================================
# 🔹 CANCELAR
# =====================================================

@app.route("/project/cancel")
def cancel_project():
    session.clear()
    return redirect(url_for("home"))

# =====================================================

if __name__ == "__main__":
    app.run(debug=True)
