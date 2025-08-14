# Demand-Calculator

This project provides tools to compute the electrical demand for single dwellings.

## Web application

The calculator now uses a React + TypeScript frontend served by a small
Flask backend.

### Backend

```
pip install flask
python app.py
```

The backend exposes a JSON API at `/api/calculate`.

### Frontend

```
cd frontend
npm install
npm run dev
```

The development server expects the Flask backend to be running on the same
host. To build a production bundle run `npm run build`.

