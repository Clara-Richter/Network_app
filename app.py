from flask import Flask, request, jsonify, render_template
from pyngrok import ngrok
import pandas as pd
from pyvis.network import Network
import html
from uuid import uuid4
import logging
import tempfile
import os
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

def validate_excel(df, sheet_name):
    """Validate that the Excel sheet contains required columns, ignoring case and whitespace."""
    logger.debug(f"Validating sheet: {sheet_name}")
    required_cols = ['Article', 'Date', f'{sheet_name} mentioned', f'{sheet_name} Sentences']
    logger.debug(f"Expected columns: {required_cols}")
    actual_cols = list(df.columns)
    logger.debug(f"Actual columns: {actual_cols}")
    
    # Create a mapping of normalized actual column names (lowercase, trimmed)
    normalized_actual_cols = {str(col).lower().strip(): col for col in actual_cols}
    missing_cols = []
    
    # Check for each required column
    for col in required_cols:
        if col.lower().strip() not in normalized_actual_cols:
            missing_cols.append(col)
    
    if missing_cols:
        logger.error(f"Missing columns: {missing_cols}")
        return False, f"Missing columns: {', '.join(missing_cols)}"
    
    # Normalize the DataFrame column names to match expected case
    df.columns = [normalized_actual_cols.get(col.lower().strip(), col) for col in df.columns]
    logger.debug(f"Normalized columns: {list(df.columns)}")
    return True, None

def save_graph(net, filename):
    """Save the network graph to a temporary file with default pyvis styles."""
    logger.debug(f"Saving graph to {filename}")
    temp_dir = tempfile.gettempdir()
    temp_filename = os.path.join(temp_dir, f"graph_{uuid4().hex}.html")
    logger.debug(f"Saving to temporary file: {temp_filename}")
    net.save_graph(temp_filename)
    with open(temp_filename, "r") as f:
        graph_html = f.read()
    os.remove(temp_filename)  # Clean up
    return graph_html

@app.route('/')
def index():
    """Render the main page."""
    logger.info("Rendering index page")
    return render_template('index.html')

@app.route('/generate-graph', methods=['POST'])
def generate_graph():
    """Generate a network graph based on the selected Excel sheet."""
    logger.info("Received request to generate graph")
    
    # Check if file is uploaded
    if 'file' not in request.files:
        logger.error("No file uploaded in request")
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    sheet_name = request.form.get('sheet_name')
    search_term = html.escape(request.form.get('search_term', ''))
    
    logger.debug(f"Sheet name: {sheet_name}")
    logger.debug(f"Search term: {search_term}")
    
    if not sheet_name:
        logger.error("No sheet name provided")
        return jsonify({"error": "No sheet name provided"}), 400

    # Read the Excel sheet
    try:
        logger.debug(f"Reading Excel sheet: {sheet_name}")
        df = pd.read_excel(file, sheet_name=sheet_name, header=0)
        logger.debug(f"Sheet {sheet_name} loaded successfully with shape: {df.shape}")
    except Exception as e:
        logger.error(f"Failed to read Excel sheet '{sheet_name}': {str(e)}")
        return jsonify({"error": f"Failed to read Excel sheet '{sheet_name}': {str(e)}"}), 400

    # Validate required columns for the sheet
    valid, error = validate_excel(df, sheet_name)
    if not valid:
        logger.error(f"Validation failed for sheet {sheet_name}: {error}")
        return jsonify({"error": error}), 400

    # Initialize network
    logger.debug("Initializing network graph")
    net = Network(height="100%", width="100%", notebook=True)

    # Root node: Sheet name (e.g., "Company", "Country", "Program")
    root_node = sheet_name
    logger.debug(f"Adding root node: {root_node}")
    net.add_node(root_node, color="blue", label=root_node)

    # First-level nodes: Unique values from "[sheet_name] mentioned"
    entities = df[f'{sheet_name} mentioned'].unique()
    logger.debug(f"Entities found: {entities}")
    for entity in entities:
        entity_str = str(entity) if pd.notnull(entity) else "Unknown Entity"
        net.add_node(entity_str, color="grey", label=entity_str)
        net.add_edge(root_node, entity_str, color="grey")

    # Second-level nodes: Articles for each entity
    logger.debug("Adding article nodes and edges")
    for idx, row in df.iterrows():
        entity = str(row[f'{sheet_name} mentioned']) if pd.notnull(row[f'{sheet_name} mentioned']) else "Unknown Entity"
        article = str(row['Article']) if pd.notnull(row['Article']) else "Unknown Article"
        sentences = row[f'{sheet_name} Sentences'] if pd.notnull(row[f'{sheet_name} Sentences']) else "No details"
        date = str(row['Date']) if pd.notnull(row['Date']) else "Unknown date"
        article_node_id = f"{entity} - {article} - {idx}"  # Ensure uniqueness with row index
        article_label = f"{article} ({date})"
        logger.debug(f"Adding article node: {article_node_id}")
        net.add_node(article_node_id, color="white", label=article_label, title=sentences)
        net.add_edge(entity, article_node_id, color="black")

    # Handle search term (highlight matching nodes)
    if search_term:
        logger.debug(f"Processing search term: {search_term}")
        df[f'{sheet_name} Sentences'] = df[f'{sheet_name} Sentences'].fillna('')
        net.add_node(search_term, color="purple", label="Search: " + search_term)
        matching_nodes = []
        for node in net.nodes:
            if 'title' in node and search_term.lower() in node['title'].lower():
                matching_nodes.append(node['id'])
        for node_id in matching_nodes:
            net.add_edge(node_id, search_term, color="black")
        logger.debug(f"Found {len(matching_nodes)} nodes matching search term")

    # Set physics options
    logger.debug("Setting physics options")
    net.set_options(json.dumps({
        "physics": {
            "barnesHut": {
                "centralGravity": 0,
                "springLength": 200,
                "avoidOverlap": 1
            },
            "minVelocity": 0.75
        }
    }))

    # Save and return graph
    filename = f"graph_{uuid4().hex}.html"
    logger.debug(f"Generated graph, saving to {filename}")
    graph_html = save_graph(net, filename)
    logger.info("Graph generated successfully")
    return graph_html

if __name__ == '__main__':
    public_url = ngrok.connect(5000)
    print(f"Public URL: {public_url}")
    logger.info("Starting Flask server")
    app.run(port=5000)
