# Guitar Pedals Database

A comprehensive Flask application for exploring, comparing, and reviewing guitar pedals.

## Features

- Browse and search through a vast collection of guitar pedals
- Detailed pedal reviews and specifications
- Side-by-side pedal comparison tool
- User ratings and reviews system
- Similar pedal recommendations
- Admin dashboard for content management
- Mobile-friendly responsive design
- SEO-optimized URLs and content

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
- Copy `.env.example` to `.env`
- Update the values in `.env` with your configuration

4. Initialize the database:
```bash
flask db upgrade
```

5. Run the application:
```bash
python app.py
```

## Deployment

### PythonAnywhere Setup

1. Upload the project files to PythonAnywhere
2. Create a virtual environment:
```bash
mkvirtualenv --python=/usr/bin/python3.10 pedals-env
pip install -r requirements.txt
```

3. Configure web app:
- Source code: `/home/yourusername/path-to-your-app`
- Working directory: `/home/yourusername/path-to-your-app`
- WSGI configuration file: Point to wsgi.py
- Virtual environment: `/home/yourusername/.virtualenvs/pedals-env`

4. Set up environment variables in the .env file
5. Configure static files in the Web tab

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
