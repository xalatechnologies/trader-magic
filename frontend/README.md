# TraderMagic Web Dashboard

This is the web dashboard for the TraderMagic system. It provides a real-time interface to monitor trading activities.

## Features

- Real-time updates via WebSocket
- Responsive design that works on desktop and mobile
- Activity history tracking
- Symbol-specific cards with trading details
- Clear visualization of buy/sell/hold decisions

## Technologies Used

- Flask for the web server
- Socket.IO for real-time updates
- Redis for data storage and pub/sub
- Modern CSS with flexbox and grid layouts
- Vanilla JavaScript (no frameworks needed)

## Development

To develop the frontend standalone:

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the Flask development server:
   ```
   python app.py
   ```

4. Access the dashboard at http://localhost:9753

## Docker

In production, the frontend is containerized and runs as part of the Docker setup described in the main README.

## Structure

- `app.py` - Main Flask application
- `templates/` - HTML templates
- `static/css/` - CSS stylesheets
- `static/js/` - JavaScript files
- `static/img/` - Images and favicon