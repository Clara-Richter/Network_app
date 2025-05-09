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
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Define a color palette for article names
COLOR_PALETTE = [
    "#FF6B6B",  # Coral
    "#4ECDC4",  # Turquoise
    "#45B7D1",  # Sky Blue
    "#96CEB4",  # Sage Green
    "#FFEEAD",  # Light Yellow
    "#D4A5A5",  # Dusty Rose
    "#9B59B6",  # Purple
    "#3498DB",  # Blue
    "#E74C3C",  # Red
    "#2ECC71",  # Green
    "#F1C40F",  # Yellow
    "#E67E22",  # Orange
]

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
    """Save the network graph to a temporary file with custom event handling."""
    logger.debug(f"Saving graph to {filename}")
    custom_js = """
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            console.log('Iframe document loaded');
            // Wait for the network to be initialized by vis.js
            const checkNetwork = setInterval(function() {
                if (typeof network !== 'undefined') {
                    clearInterval(checkNetwork);
                    console.log('Network object found:', network);
                    // Force the network to fit the container
                    network.fit();
                    // Add selectNode event listener
                    network.on('selectNode', function(params) {
                        console.log('selectNode event triggered:', params);
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            const node = network.body.nodes[nodeId];
                            console.log('Selected node:', node);
                            // Check if the node is an article node (square shape)
                            if (node.options.shape === 'square') {
                                const sentences = node.options.title || 'No sentences available.';
                                const articleLabel = node.options.label || 'Unknown Article';
                                console.log('Article node selected, label:', articleLabel);
                                // Find the entity node this article node is connected to
                                let entityName = 'Unknown Entity';
                                const edges = network.getConnectedEdges(nodeId);
                                for (let edgeId of edges) {
                                    const edge = network.body.edges[edgeId];
                                    const fromNode = network.body.nodes[edge.fromId];
                                    // The entity node should not be the root (e.g., "Company") and not a search term (purple)
                                    if (fromNode.options.shape !== 'square' && fromNode.options.color !== 'purple' && fromNode.options.color !== 'blue') {
                                        entityName = fromNode.options.label || 'Unknown Entity';
                                        break;
                                    }
                                }
                                console.log('Entity name:', entityName);
                                // Send the sentences, article label, and entity name to the parent window
                                window.parent.postMessage({
                                    type: 'showArticleSentences',
                                    sentences: sentences,
                                    articleLabel: articleLabel,
                                    entityName: entityName
                                }, '*');
                            } else {
                                console.log('Selected node is not an article node:', node.options);
                            }
                        } else {
                            console.log('No nodes selected in selectNode event');
                        }
                    });
                } else {
                    console.log('Network object not found yet...');
                }
            }, 100); // Check every 100ms until network is found
        });
    </script>
    """
    temp_dir = tempfile.gettempdir()
    temp_filename = os.path.join(temp_dir, f"graph_{uuid4().hex}.html")
    logger.debug(f"Saving to temporary file: {temp_filename}")
    net.save_graph(temp_filename)
    with open(temp_filename, "r") as f:
        graph_html = f.read()
    # Inject the custom JavaScript before the closing </body> tag
    graph_html = graph_html.replace('</body>', custom_js + '</body>')
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

    # Initialize network with fixed pixel height and full width
    logger.debug("Initializing network graph")
    net = Network(height="590px", width="100%", notebook=True)

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

    # Map article names to colors
    article_to_color = {}
    unique_articles = df['Article'].unique()
    logger.debug(f"Unique articles: {unique_articles}")
    for idx, article in enumerate(unique_articles):
        article_str = str(article) if pd.notnull(article) else "Unknown Article"
        color = COLOR_PALETTE[idx % len(COLOR_PALETTE)]  # Cycle through the palette
        article_to_color[article_str] = color
        logger.debug(f"Assigned color {color} to article '{article_str}'")

    # Second-level nodes: Articles for each entity
    logger.debug("Adding article nodes and edges")
    for idx, row in df.iterrows():
        entity = str(row[f'{sheet_name} mentioned']) if pd.notnull(row[f'{sheet_name} mentioned']) else "Unknown Entity"
        article = str(row['Article']) if pd.notnull(row['Article']) else "Unknown Article"
        sentences = row[f'{sheet_name} Sentences'] if pd.notnull(row[f'{sheet_name} Sentences']) else "No details"
        date = row['Date']
        # Format the date to "Feb. 27, 2025"
        if pd.notnull(date):
            try:
                date_obj = pd.to_datetime(date)
                date_str = date_obj.strftime("%b. %d, %Y")
            except Exception as e:
                logger.warning(f"Failed to format date '{date}': {str(e)}")
                date_str = "Unknown date"
        else:
            date_str = "Unknown date"
        article_node_id = f"{entity} - {article} - {idx}"  # Ensure uniqueness with row index
        article_label = f"{article} ({date_str})"
        # Get the color for this article name
        article_color = article_to_color[article]
        logger.debug(f"Adding article node: {article_node_id} with color {article_color}")
        net.add_node(article_node_id, color=article_color, shape="square", label=article_label, title=sentences)
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
        "enabled": True,  # Keep physics enabled for initial layout
        "barnesHut": {
            "centralGravity": 0.1,  # Slight pull to keep nodes cohesive
            "springLength": 100,    # Shorter springs for tighter layout
            "springConstant": 0.1,  # Stiffer springs to reduce movement
            "damping": 0.5,         # Higher damping to reduce oscillations
            "avoidOverlap": 1       # Keep this to prevent node overlap
        },
        "minVelocity": 1,           # Higher to stop movement sooner
        "stabilization": {
            "enabled": True,        # Enable stabilization
            "iterations": 1000      # Number of iterations for precomputing positions
        }
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
