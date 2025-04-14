from flask import Flask, request, jsonify, render_template
import pandas as pd
from pyvis.network import Network
import json
import html  # Import the HTML module for escaping


app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-IOgraph', methods=['POST'])
def generate_IOgraph():
    if 'file' not in request.files:
        return "No file uploaded"

    file = request.files['file']
    all_components = ['D', 'O', 'T', 'm', 'L', 'Pr', 'F', 'Po']
    df = pd.read_excel(file, header=2)
    search_term = request.form.get('search_term', '')

    data = json.loads(request.form['checkboxState']) if 'checkboxState' in request.form else {}

    if data:
        checked_components = [component for component, checked in data.items() if checked]
        unchecked_components = [component for component in all_components if component not in checked_components]
        mask = ~df['DOTmLPFP'].isin(unchecked_components)
        df = df[mask]

    net = Network(height="590px", width="100%", notebook=True, cdn_resources='remote')
    programs = df['Programs'].unique()
    for program in programs:
        color = 'grey' if program not in df.iloc[:, 1].values else 'white'
        net.add_node(program, color=color)

    for _, row in df.iterrows():
        col2 = f"{row['Programs']} - {row.iloc[1]}"
        title = row['Rationale'] if pd.notnull(row['Rationale']) else " "
        color = 'white'
        if row['Status'] == 'Green':
            color = 'green'
        elif row['Status'] == 'Yellow':
            color = 'yellow'
        elif row['Status'] == 'Red':
            color = 'red'
        net.add_node(col2, color=color, label=row.iloc[1], title=title)

    for _, row in df.iterrows():
        col2 = f"{row['Programs']} - {row.iloc[1]}"
        net.add_edge(row['Programs'], col2)

    if search_term:
        df['Rationale'] = df['Rationale'].fillna('')
        net.add_node(search_term, color="purple")
        matching_nodes = []
        for node in net.nodes:
            if 'title' in node.keys() and search_term in node['title']:
                matching_nodes.append(node['id'])
        for nodes in matching_nodes:
            net.add_edge(nodes, search_term, color="black")

    net.add_node("Missile Defense", color="blue")
    for root_node in programs:
        net.add_edge(root_node, "Missile Defense")

    options = {
        "physics": {
            "barnesHut": {
                "centralGravity": 0
            },
            "minVelocity": 0.75
        }
    }

    legend_html = """
        <!-- Legend -->
        <div class="legend" style="position: absolute; top: 20px; left: 1%;">
            <div class="legend-item">
                <div class="legend-color" style="background-color: green;"></div>
                Assessment On Track
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: yellow;"></div>
                Assessment Issues
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: red;"></div>
                Assessment Critical Issues
            </div>
        </div>
    """

    filename = "static/network.html"
    net.save_graph(filename)

    with open(filename, "w") as f:
        f.write("<html>\n<style>\n")
        f.write(".legend { position: absolute; top: 20px; left: 1%; background-color: rgba(255, 255, 255, 0.8); border: 1px solid #999; padding: 8px; font-family: Arial, sans-serif; font-size: 12px; }")
        f.write(".legend-item { margin-bottom: 5px; }")
        f.write(".legend-color { display: inline-block; width: 10px; height: 10px; margin-right: 5px; border: 1px solid #999; }")
        f.write("</style>\n")
        f.write(net.html)
        f.write("\n")
        f.write(legend_html)

    with open(filename, "r") as f:
        graph_html = f.read()

    return graph_html

#### Preformance growth
@app.route('/generate-GrowthGraph', methods=['POST'])
def generate_GrowthGraph():
    if 'file' not in request.files:
        return "No file uploaded"

    file = request.files['file']
    df = pd.read_excel(file, header=0)

    net = Network(height="600px", width="100%", notebook=True, cdn_resources='remote')
    programs = df['Program'].unique()

    for _, row in df.iterrows():
        if "$" in row[1]:
            performance = 'Cost Growth'
        else:
            performance = 'Schedule Growth'
            
        color = 'white'
        if row['Status'] == 'Green':
            color = 'green'
        elif row['Status'] == 'Yellow':
            color = 'yellow'
        elif row['Status'] == 'Red':
            color = 'red'
        node_label = f"Obj.: {row[1]}\nThold.: {row[2]}\nPM Est.: {row['PM Estimate']}\nTrend: {row['Trend']}"
        net.add_node(row['Program'], color=color, title=node_label)

    # Define a unique identifier for the performance node
    performance_node_id = "PerformanceNode"
    # Add the performance node with a label
    net.add_node(performance_node_id, label=performance, color="grey")
    for nodes in programs:
        net.add_edge(nodes, performance_node_id, color="grey")

    options = {
        "physics": {
            "barnesHut": {
                "centralGravity": 0},
            "minVelocity": 0.75
        }
    }

    legend_html = """
        <!-- Legend -->
        <div class="legend" style="position: absolute; top: 20px; left: 1%;">
            <div class="legend-item">
                <div class="legend-color" style="background-color: green;"></div>
                At/Within APB Objective
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: yellow;"></div>
                At/Within APB Threshold
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: red;"></div>
                Breached APB Threshold
            </div>
        </div>
    """
    
    filename = "static/Growth.html"
    net.save_graph(filename)

    with open(filename, "w") as f:
        f.write("<html>\n<style>\n")
        f.write(".legend { position: absolute; top: 20px; left: 1%; background-color: rgba(255, 255, 255, 0.8); border: 1px solid #999; padding: 8px; font-family: Arial, sans-serif; font-size: 16px; }")
        f.write(".legend-item { margin-bottom: 5px; }")
        f.write(".legend-color { display: inline-block; width: 10px; height: 10px; margin-right: 5px; border: 1px solid #999; }")
        f.write("</style>\n")
        f.write(net.html)
        f.write("\n")
        f.write(legend_html)

    with open(filename, "r") as f:
        graph_html = f.read()

    return graph_html

def add_line_breaks(text, words_per_line=7):
    words = text.split()
    lines = [' '.join(words[i:i + words_per_line]) for i in range(0, len(words), words_per_line)]
    return '<br>'.join(lines)

#### HAR
@app.route('/generate-HARGraph', methods=['POST'])
def generate_HARGraph():
    if 'file' not in request.files:
        return "No file uploaded"

    file = request.files['file']
    df = pd.read_excel(file, header=0)
    search_term = request.form.get('search_term', '')

    net = Network(height="600px", width="100%", notebook=True, cdn_resources='remote')
    programs = df['Program'].unique()

    
    if df.columns[2] == 'Cost Rationale':
        performance = 'Cost HAR'
    else:
        performance = 'Schedule HAR'

    # Add nodes for each program with color according to status
    for _, row in df.iterrows():
        color = 'white'  # Default color
        if row['Status'] == 'Green':
            color = 'green'
        elif row['Status'] == 'Yellow':
            color = 'yellow'
        elif row['Status'] == 'Red':
            color = 'red'
        # Define the node label and hover details
        node_label = f"{row[2]}"
        net.add_node(row['Program'], color=color, title=node_label)

    if search_term:
        df[df.columns[2]] = df[df.columns[2]].fillna('')
        net.add_node(search_term, color="purple")
        matching_nodes = []
        search_term_lower = search_term.lower()
        for node in net.nodes:
            if 'title' in node.keys() and search_term_lower in node['title'].lower():
                matching_nodes.append(node['id'])
        for nodes in matching_nodes:
            net.add_edge(nodes, search_term, color="black")

    # Add a node named "HAR"
    net.add_node(performance, color="grey")

    # Connect all nodes to the "HAR" node
    for nodes in programs:
        net.add_edge(nodes, performance, color="grey")

    options = {
        "physics": {
            "barnesHut": {
                "centralGravity": 0
            },
            "minVelocity": 0.75
        }
    }

    # HTML code for legend
    legend_html = """
        <!-- Legend -->
        <div class="legend" style="position: absolute; top: 20px; left: 1%;">
            <div class="legend-item">
                <div class="legend-color" style="background-color: green;"></div>
                Source Reports No Issues in HAR
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: yellow;"></div>
                Source Reports Issues in HAR
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: red;"></div>
                Source Reports Significant Issues in HAR
            </div>
        </div>
    """

    filename = "static/hsa.html"
    net.save_graph(filename)

    # Custom CSS for tooltips and legend
    custom_css = """
    <style>
    .vis-tooltip {
        max-width: 300px;
        text-wrap: wrap !important;
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

    with open(filename, "w") as f:
        f.write("<html>\n")
        # f.write(".legend { position: absolute; top: 20px; left: 1%; background-color: rgba(255, 255, 255, 0.8); border: 1px solid #999; padding: 8px; font-family: Arial, sans-serif; font-size: 16px; }")
        # f.write(".legend-item { margin-bottom: 5px; }")
        # f.write(".legend-color { display: inline-block; width: 10px; height: 10px; margin-right: 5px; border: 1px solid #999; }")
        f.write(custom_css)
        f.write(net.html)
        f.write(legend_html)
        f.write("</html>")

    with open(filename, "r") as f:
        graph_html = f.read()

    return graph_html


@app.route('/update-graph', methods=['POST'])
def update_graph():
    data = request.json
    all_components = ['D', 'O', 'T', 'm', 'L', 'Pr', 'F', 'Po']
    checked_components = [component for component, checked in data.items() if checked]
    unchecked_components = [component for component in all_components if component not in checked_components]
    return generate_IOgraph(unchecked_components)

if __name__ == '__main__':
    app.run(debug=True)
