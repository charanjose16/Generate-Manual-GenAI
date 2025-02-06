import { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [productName, setProductName] = useState('');
  const [summary, setSummary] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Call the FastAPI endpoint using POST
      const response = await axios.post(
        'http://localhost:8000/generate-manual', // Endpoint URL
        {
          product_name: productName,
          summary,
        },
        {
          responseType: 'blob', // Important for handling binary data (PDF)
        }
      );

      // Create a download link for the PDF
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'user_manual.pdf'); // Filename
      document.body.appendChild(link);
      link.click();
      link.remove();

      setLoading(false);
    } catch (err) {
      console.error('Error generating manual:', err);
      setError('An error occurred while generating the manual. Please try again.');
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <h1>User Manual Generator</h1>
      <p>Create a professional user manual in PDF format by providing the product details below.</p>
      <form onSubmit={handleSubmit} className="form-container">
        <div className="input-group">
          <label htmlFor="product-name">Product Name:</label>
          <input
            type="text"
            id="product-name"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            placeholder="Enter product name"
            required
          />
        </div>
        <div className="input-group">
          <label htmlFor="summary">Product Summary:</label>
          <textarea
            id="summary"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="Enter a brief summary of the product"
            rows="4"
            required
          />
        </div>
        {error && <p className="error-message">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? 'Generating Manual...' : 'Generate Manual'}
        </button>
      </form>
    </div>
  );
}

export default App;