from flask import Flask, request, jsonify, render_template
from pyngrok import ngrok
import pandas as pd
from pyvis.network import Network
import html
from uuid import uuid4

app = Flask(__name__)

def validate_excel(df, sheet_name):
    """Validate that the Excel sheet contains required columns."""
    required_cols = ['Article', 'Date', f'{sheet_name} mentioned', f'{sheet_name} Sentences']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return False, f"Missing columns: {', '.join(missing_cols)}"
    return True, None

def save_graph_with_legend(net, filename, legend_html):
    """Save the network graph with custom CSS and legend."""
    custom_css = """
    <style>
        .vis-tooltip {
            max-width: 300px;
            white-space: pre-wrap;
            font-family: Arial, sans-serif;
            font-size: 14px;
        }
        .legend {
            position: absolute;
            top: 20px;
            left: 1%;
            background-color: rgba(255, 255, 255, 0.8);
            border: 1px solid #999;
            padding: 8px;
            font-family: Arial, sans-serif;
            font-size: 14px;
        }
        .legend-item {
            margin-bottom: 5px;
        }
        .legend-color {
            display: inline-block;
            width: 10px;
            height: 10px;
            margin-right: 5px;
            border: 1px solid #999;
        }
    </style>
    """
    net.save_graph(filename)
    with open(filename, "w") as f:
        f.write("<html>\n")
        f.write(custom_css)
        f.write(net.html)
        f.write(legend_html)
        f.write("</html>")
    with open(filename, "r") as f:
        return f.read()

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/generate-graph', methods=['POST'])
def generate_graph():
    """Generate a network graph based on the selected Excel sheet."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    sheet_name = request.form.get('sheet_name')
    search_term = html.escape(request.form.get('search_term', ''))

    try:
        df = pd.read_excel(file, sheet_name=sheet_name, header=0)
    except Exception as e:
        return jsonify({"error": f"Failed to read Excel sheet '{sheet_name}': {str(e)}"}), 400

    # Validate required columns for the sheet
    valid, error = validate_excel(df, sheet_name)
    if not valid:
        return jsonify({"error": error}), 400

    # Initialize network
    net = Network(height="590px", width="100%", notebook=True, cdn_resources='remote')

    # Root node: Sheet name (e.g., "Company", "Country", "Program")
    root_node = sheet_name
    net.add_node(root_node, color="blue", label=root_node)

    # First-level nodes: Unique values from "[sheet_name] mentioned"
    entities = df[f'{sheet_name} mentioned'].unique()
    for entity in entities:
        net.add_node(entity, color="grey", label=entity)
        net.add_edge(root_node, entity, color="grey")

    # Second-level nodes: Articles for each entity
    for _, row in df.iterrows():
        entity = row[f'{sheet_name} mentioned']
        article = row['Article']
        sentences = row[f'{sheet_name} Sentences'] if pd.notnull(row[f'{sheet_name} Sentences']) else "No details"
        date = row['Date'] if pd.notnull(row['Date']) else "Unknown date"
        article_node_id = f"{entity} - {article}"
        # Include the date in the label for more context
        article_label = f"{article} ({date})"
        net.add_node(article_node_id, color="white", label=article_label, title=sentences)
        net.add_edge(entity, article_node_id, color="black")

    # Handle search term (highlight matching nodes)
    if search_term:
        df[f'{sheet_name} Sentences'] = df[f'{sheet_name} Sentences'].fillna('')
        net.add_node(search_term, color="purple", label="Search: " + search_term)
        matching_nodes = []
        for node in net.nodes:
            if 'title' in node and search_term.lower() in node['title'].lower():
                matching_nodes.append(node['id'])
        for node_id in matching_nodes:
            net.add_edge(node_id, search_term, color="black")

    # Set physics options
    net.set_options(json.dumps({
        "physics": {
            "barnesHut": {"centralGravity": 0},
            "minVelocity": 0.75
        }
    }))

    # Define legend
    legend_html = """
    <div class="legend">
        <div class="legend-item"><div class="legend-color" style="background-color: blue;"></div>Root Node</div>
        <div class="legend-item"><div class="legend-color" style="background-color: grey;"></div>Entities</div>
        <div class="legend-item"><div class="legend-color" style="background-color: white;"></div>Articles</div>
        <div class="legend-item"><div class="legend-color" style="background-color: purple;"></div>Search Term</div>
    </div>
    """

    # Save and return graph
    filename = f"static/graph_{uuid4().hex}.html"
    graph_html = save_graph_with_legend(net, filename, legend_html)
    return graph_html

if __name__ == '__main__':
    public_url = ngrok.connect(5000)
    print(f"Public URL: {public_url}")
    app.run(port=5000)
