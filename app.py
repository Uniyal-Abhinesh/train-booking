
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_mysqldb import MySQL
import heapq
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Cobrakai@123'
app.config['MYSQL_DB'] = 'train'

mysql = MySQL(app)

class TrainPathFinder:
    def __init__(self, mysql_connection):
        self.mysql = mysql_connection

    def get_all_stations(self):
        """Get all stations from database"""
        cur = self.mysql.connection.cursor()
        cur.execute("SELECT id, station_code, station_name, city FROM stations")
        stations = cur.fetchall()
        cur.close()
        return stations

    def get_station_connections(self):
        """Get all station connections for building graph"""
        cur = self.mysql.connection.cursor()
        cur.execute("""
            SELECT from_station_id, to_station_id, distance, travel_time 
            FROM station_connections
        """)
        connections = cur.fetchall()
        cur.close()
        return connections

    def build_graph(self):
        """Build adjacency list representation of the railway network"""
        connections = self.get_station_connections()
        graph = {}
        
        for from_station, to_station, distance, travel_time in connections:
            if from_station not in graph:
                graph[from_station] = []
            graph[from_station].append((to_station, distance, travel_time))
            
        return graph

    def dijkstra_shortest_path(self, start_station_id, end_station_id, metric='distance'):
        """
        Find shortest path using Dijkstra's algorithm
        metric: 'distance' or 'time'
        """
        graph = self.build_graph()
        
        # Priority queue: (cost, current_station, path)
        pq = [(0, start_station_id, [start_station_id])]
        visited = set()
        distances = {start_station_id: 0}
        
        while pq:
            current_cost, current_station, path = heapq.heappop(pq)
            
            if current_station in visited:
                continue
                
            visited.add(current_station)
            
            if current_station == end_station_id:
                return {
                    'path': path,
                    'total_cost': current_cost,
                    'metric': metric
                }
            
            if current_station in graph:
                for neighbor, distance, travel_time in graph[current_station]:
                    if neighbor not in visited:
                        # Choose cost based on metric
                        edge_cost = distance if metric == 'distance' else travel_time
                        total_cost = current_cost + edge_cost
                        
                        if neighbor not in distances or total_cost < distances[neighbor]:
                            distances[neighbor] = total_cost
                            new_path = path + [neighbor]
                            heapq.heappush(pq, (total_cost, neighbor, new_path))
        
        return None  # No path found

    def get_trains_on_route(self, station_path):
        """Find trains that cover the given route"""
        if len(station_path) < 2:
            return []
        
        cur = self.mysql.connection.cursor()
        
        # Find trains that pass through the start and end stations
        query = """
            SELECT DISTINCT t.id, t.train_number, t.train_name, t.train_type,
                   s1.station_name as source_name, s2.station_name as dest_name,
                   tr1.departure_time as source_dept, tr2.arrival_time as dest_arr,
                   tr2.fare_from_source - tr1.fare_from_source as fare
            FROM trains t
            JOIN train_routes tr1 ON t.id = tr1.train_id
            JOIN train_routes tr2 ON t.id = tr2.train_id
            JOIN stations s1 ON tr1.station_id = s1.id
            JOIN stations s2 ON tr2.station_id = s2.id
            WHERE tr1.station_id = %s 
            AND tr2.station_id = %s
            AND tr1.sequence_number < tr2.sequence_number
            ORDER BY fare ASC
        """
        
        start_station = station_path[0]
        end_station = station_path[-1]
        
        cur.execute(query, (start_station, end_station))
        trains = cur.fetchall()
        cur.close()
        
        return trains

    def get_station_details(self, station_ids):
        """Get station details for given station IDs"""
        if not station_ids:
            return {}
        
        cur = self.mysql.connection.cursor()
        placeholders = ','.join(['%s'] * len(station_ids))
        query = f"""
            SELECT id, station_code, station_name, city 
            FROM stations 
            WHERE id IN ({placeholders})
        """
        cur.execute(query, station_ids)
        stations = cur.fetchall()
        cur.close()
        
        return {station[0]: station for station in stations}

# Initialize path finder
path_finder = TrainPathFinder(mysql)

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        phone = request.form['phone']

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            existing_user = cur.fetchone()
            if existing_user:
                flash('Username already exists! Choose another.')
                cur.close()
                return redirect(url_for('register'))

            cur.execute(
                "INSERT INTO users (username, password, email, phone) VALUES (%s, %s, %s, %s)",
                (username, password, email, phone)
            )
            mysql.connection.commit()
            cur.close()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))

        except Exception as e:
            flash('An error occurred while registering. Please try again.')
            return redirect(url_for('register'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
            user = cur.fetchone()
            cur.close()

            if user:
                return redirect(url_for('dashboard', username=username))
            else:
                flash('Invalid username or password.')
                return redirect(url_for('login'))

        except Exception as e:
            flash('An error occurred during login. Please try again.')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    username = request.args.get('username')
    if not username:
        flash('Please log in first.')
        return redirect(url_for('login'))
    
    # Get all stations for dropdown
    stations = path_finder.get_all_stations()
    return render_template('dashboard.html', username=username, stations=stations)

@app.route('/find_route', methods=['POST'])
def find_route():
    """Find shortest route and available trains"""
    username = request.form.get('username')
    source_id = int(request.form.get('source_station'))
    destination_id = int(request.form.get('destination_station'))
    metric = request.form.get('metric', 'distance')  # 'distance' or 'time'
    
    if not username:
        flash('Please log in first.')
        return redirect(url_for('login'))
    
    # Find shortest path
    shortest_path = path_finder.dijkstra_shortest_path(source_id, destination_id, metric)
    
    if not shortest_path:
        flash('No route found between selected stations.')
        return redirect(url_for('dashboard', username=username))
    
    # Get station details
    station_details = path_finder.get_station_details(shortest_path['path'])
    
    # Get available trains
    available_trains = path_finder.get_trains_on_route(shortest_path['path'])
    
    # Prepare route information
    route_info = {
        'path': [station_details[sid] for sid in shortest_path['path']],
        'total_cost': shortest_path['total_cost'],
        'metric': shortest_path['metric'],
        'trains': available_trains
    }
    
    stations = path_finder.get_all_stations()
    return render_template('route_results.html', 
                         username=username, 
                         route_info=route_info,
                         stations=stations,
                         source_id=source_id,
                         destination_id=destination_id)

@app.route('/book', methods=['POST'])
def book_ticket():
    username = request.form.get('username')
    if not username:
        flash('Please log in first.')
        return redirect(url_for('login'))

    train_id = request.form.get('train_id')
    passenger_name = request.form['passenger_name']
    source_station_id = request.form['source_station_id']
    destination_station_id = request.form['destination_station_id']
    journey_date = request.form['journey_date']
    fare = request.form.get('fare', 0)

    try:
        cur = mysql.connection.cursor()
        
        # Generate seat number (simple implementation)
        cur.execute("SELECT COUNT(*) FROM tickets WHERE train_id=%s AND journey_date=%s", 
                   (train_id, journey_date))
        seat_count = cur.fetchone()[0]
        seat_number = f"S{(seat_count + 1):03d}"
        
        cur.execute("""
            INSERT INTO tickets (username, passenger_name, train_id, source_station_id, 
                               destination_station_id, journey_date, seat_number, fare)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (username, passenger_name, train_id, source_station_id, 
              destination_station_id, journey_date, seat_number, fare))
        
        mysql.connection.commit()
        ticket_id = cur.lastrowid
        cur.close()
        
        flash(f'Ticket booked successfully! Ticket ID: {ticket_id}, Seat: {seat_number}')
        return redirect(url_for('dashboard', username=username))

    except Exception as e:
        flash('An error occurred while booking the ticket. Please try again.')
        return redirect(url_for('dashboard', username=username))

@app.route('/my_tickets')
def my_tickets():
    username = request.args.get('username')
    if not username:
        flash('Please log in first.')
        return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT t.id, t.passenger_name, tr.train_number, tr.train_name,
                   s1.station_name as source, s2.station_name as destination,
                   t.journey_date, t.seat_number, t.fare, t.status
            FROM tickets t
            JOIN trains tr ON t.train_id = tr.id
            JOIN stations s1 ON t.source_station_id = s1.id
            JOIN stations s2 ON t.destination_station_id = s2.id
            WHERE t.username = %s
            ORDER BY t.booking_date DESC
        """, (username,))
        tickets = cur.fetchall()
        cur.close()
        
        return render_template('my_tickets.html', username=username, tickets=tickets)
        
    except Exception as e:
        flash('Error retrieving tickets.')
        return redirect(url_for('dashboard', username=username))

@app.route('/api/stations')
def api_stations():
    """API endpoint to get all stations"""
    stations = path_finder.get_all_stations()
    return jsonify([{
        'id': station[0],
        'code': station[1],
        'name': station[2],
        'city': station[3]
    } for station in stations])

@app.route('/logout')
def logout():
    flash('Logged out successfully.')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
