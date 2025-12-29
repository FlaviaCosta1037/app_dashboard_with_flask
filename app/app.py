from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import json
import os
import uuid

app = Flask(__name__)
app.secret_key = "dev-secret-key-v2"
UPLOAD_FOLDER = "app/data"
def load_table(path):
    ext = os.path.splitext(path)[1].lower()

    if ext == ".csv":
        try:
            return pd.read_csv(path, encoding="utf-8", sep=None, engine="python")
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="latin1", sep=None, engine="python")
        except Exception:
            return pd.read_csv(
                path,
                encoding="latin1",
                sep=";",
                engine="python",
                on_bad_lines="skip"
            )

    elif ext in [".xlsx", ".xls"]:
        return pd.read_excel(path)

    else:
        raise ValueError(f"Formato de arquivo não suportado: {ext}")

def process_dates(df, column_types):

    for col, col_type in column_types.items():
        if col_type == "date":
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            df[f"{col}_year"] = df[col].dt.year
            df[f"{col}_month"] = df[col].dt.month
            df[f"{col}_day"] = df[col].dt.day
    return df
@app.route("/", methods=["GET"])
def new_project():
    session.clear()
    return render_template("new_project.html")

        
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            return "Nenhum arquivo enviado", 400

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{file.filename}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)

        # 🔹 LEITURA DO ARQUIVO
        try:
            if filename.lower().endswith(".csv"):
                try:
                    df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(path, sep=None, engine="python", encoding="latin1")

            elif filename.lower().endswith((".xls", ".xlsx")):
                df = pd.read_excel(path)

            else:
                return "Formato de arquivo não suportado", 400

        except Exception as e:
            return f"Erro ao ler arquivo: {e}", 500

        session.clear()  # limpa projeto anterior
        session["file_path"] = path
        session["columns"] = df.columns.tolist()

        return redirect(url_for("define_columns"))

    return render_template("upload.html")



@app.route("/columns", methods=["GET", "POST"])
def define_columns():
    columns = session["columns"]

    if request.method == "POST":
        column_types = {c: request.form.get(c) for c in columns}
        session["column_types"] = column_types
        return redirect(url_for("new_visual"))

    return render_template("columns.html", columns=columns)

@app.route("/visual/new", methods=["GET", "POST"])
def new_visual():
    file_path = session.get("file_path")
    column_types = session.get("column_types")

    if not file_path or not column_types:
        return redirect(url_for("upload"))

    df = load_table(file_path)

    categories = [c for c, t in column_types.items() if t in ["category", "date"]]
    numbers = [c for c, t in column_types.items() if t == "number"]

    if request.method == "POST":
        chart_type = request.form["chart_type"]
        x = request.form["x"]
        y = request.form["y"]
        legends = request.form.getlist("legends")

        charts = session.get("charts", [])

        # 🔥 AQUI o chart_config É CRIADO
        if legends:
            datasets = []
            for value in df[legends[0]].dropna().unique():
                subset = df[df[legends[0]] == value]
                grouped = subset.groupby(x)[y].sum().reset_index()

                datasets.append({
                    "label": str(value),
                    "data": grouped[y].tolist()
                })

            chart_config = {
                "type": chart_type,
                "labels": grouped[x].astype(str).tolist(),
                "datasets": datasets
            }

        else:
            grouped = df.groupby(x)[y].sum().reset_index()
            chart_config = {
                "type": chart_type,
                "labels": grouped[x].astype(str).tolist(),
                "datasets": [{
                    "label": y,
                    "data": grouped[y].tolist()
                }]
            }

        # ✅ AGORA SIM: chart_config EXISTE
        charts.append(chart_config)
        session["charts"] = charts

        return redirect(url_for("dashboard"))

    return render_template(
        "visual_new.html",
        categories=categories,
        numbers=numbers
    )

@app.route("/dashboard")
def dashboard():
    charts = session.get("charts", [])
    return render_template("dashboard.html", charts=charts)

@app.route("/cancel")
def cancel_project():
    session.clear()
    return redirect(url_for("new_project"))



if __name__ == "__main__":
    app.run(debug=True)
