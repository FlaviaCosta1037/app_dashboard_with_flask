from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import json
import os
import uuid

app = Flask(__name__)
app.secret_key = "dev-secret-key-v2"
UPLOAD_FOLDER = "app/data"

@app.route("/", methods=["GET", "POST"])
def load_csv(path):
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
def process_dates(df, column_types):

    for col, col_type in column_types.items():
        if col_type == "date":
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            df[f"{col}_year"] = df[col].dt.year
            df[f"{col}_month"] = df[col].dt.month
            df[f"{col}_day"] = df[col].dt.day
    return df
        
def upload():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            return "Nenhum arquivo enviado", 400

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # gera nome único para evitar conflito
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{file.filename}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)

        # tenta ler o CSV de forma robusta
        try:
            df = pd.read_csv(path, encoding="utf-8", sep=None, engine="python")
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding="latin1", sep=None, engine="python")
        except Exception:
            df = pd.read_csv(
                path,
                encoding="latin1",
                sep=";",
                engine="python",
                engine_kwargs={"on_bad_lines": "skip"}
            )

        session["file_path"] = path
        session["columns"] = list(df.columns)

        return redirect(url_for("define_columns"))

    return render_template("upload.html")


@app.route("/columns", methods=["GET", "POST"])
def define_columns():
    columns = session.get("columns")

    if request.method == "POST":
        column_types = {}
        for col in columns:
            column_types[col] = request.form.get(col)

        session["column_types"] = column_types
        return redirect(url_for("choose_chart"))

    return render_template("columns.html", columns=columns)


@app.route("/charts", methods=["GET", "POST"])
def choose_chart():
    if request.method == "POST":
        session["chart_type"] = request.form["chart"]
        return redirect(url_for("visualize"))

    return render_template("charts.html")


@app.route("/visualize", methods=["GET", "POST"])
def visualize():
    path = session.get("file_path")
    column_types = session.get("column_types")
    chart_type = session.get("chart_type")

    if not path or not column_types or not chart_type:
        return redirect(url_for("upload"))

    df = load_csv(path)
    df = process_dates(df, column_types)

    categories = []
    numbers = []

    for col, col_type in column_types.items():
        if col_type == "category":
            categories.append(col)

        elif col_type == "number":
            numbers.append(col)

        elif col_type == "date":
            categories.extend([
                f"{col}_year",
                f"{col}_month",
                f"{col}_day"
            ])


    chart_data = {}

    if request.method == "POST":
        x = request.form.get("x")
        y = request.form.get("y")

        if x and y:
            grouped = df.groupby(x)[y].sum().reset_index()

            chart_data = {
                "labels": grouped[x].astype(str).tolist(),
                "values": grouped[y].astype(int).tolist()
            }

            if chart_type == "stacked":
                chart_type = "bar"

    return render_template(
        "visualize.html",
        chart_type=chart_type,
        chart_data=json.dumps(chart_data),
        categories=categories,
        numbers=numbers
    )


if __name__ == "__main__":
    app.run(debug=True)
