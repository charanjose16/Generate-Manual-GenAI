import { useState, useEffect } from "react";
import {
  
  Select,
  MenuItem,
  Button,
  Grid,
  Box,
  Typography,
} from "@mui/material";

export default function UserManualGenerator() {
  const [language, setLanguage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [selectedSubProduct, setSelectedSubProduct] = useState("");
  const [uploadedFile, setUploadedFile] = useState(null);

  // Fetch products data from the FastAPI backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/products");
        if (!response.ok) {
          throw new Error("Failed to fetch products");
        }
        const data = await response.json();
        setProducts(data.products); // Assuming the API returns { products: [...] }
      } catch (err) {
        setError(`Failed to load products: ${err.message}`);
      }
    };
    fetchData();
  }, []);

  const handleProductChange = (event) => {
    const productName = event.target.value;
    setSelectedProduct(productName);
    setSelectedSubProduct(""); // Reset sub-product when main product changes
    if (error) setError("");
  };

  const handleSubProductChange = (event) => {
    setSelectedSubProduct(event.target.value);
    if (error) setError("");
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file && file.type === "application/pdf") {
      setUploadedFile(file);
      setError("");
    } else {
      setError("Please upload a valid PDF file.");
      setUploadedFile(null);
    }
  };

  const handleGenerateManual = async () => {
    if (!language || !selectedProduct || !uploadedFile) {
      setError("Please fill in all required fields and upload a PDF file.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("product_category", selectedProduct);
      formData.append("rag_source", uploadedFile);
      formData.append("language", language.trim());

      const response = await fetch("http://localhost:8000/generate-manual", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || "Failed to generate manual");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `user_manual_${language}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setSelectedProduct("");
      setSelectedSubProduct("");
      setUploadedFile(null);
      setLanguage("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        height: "100vh",
        width: "100vw",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        p: 3,
        bgcolor: "background.paper",
      }}
    >
      <Typography
        variant="h4"
        component="h1"
        align="center"
        sx={{
          mb: 4,
          fontWeight: "bold",
          color: "text.primary",
        }}
      >
        User Manual Generator
      </Typography>
      <Grid container spacing={3} sx={{ maxWidth: 600 }}>
        {/* Product Selection */}
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Product
          </Typography>
          <Select
            fullWidth
            value={selectedProduct}
            onChange={handleProductChange}
            displayEmpty
            variant="outlined"
            disabled={loading}
          >
            <MenuItem value="" disabled>
              Select a product
            </MenuItem>
            {products.map((product, index) => (
              <MenuItem key={index} value={product.product_name}>
                {product.product_name}
              </MenuItem>
            ))}
          </Select>
        </Grid>

        {/* Sub-Product Dropdown */}
        {selectedProduct && (
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom>
              Sub-Product
            </Typography>
            <Select
              fullWidth
              value={selectedSubProduct}
              onChange={handleSubProductChange}
              displayEmpty
              variant="outlined"
              disabled={loading}
            >
              <MenuItem value="" disabled>
                Select a sub-product
              </MenuItem>
              {products
                .find((p) => p.product_name === selectedProduct)
                ?.subproducts.map((subproduct, index) => (
                  <MenuItem key={index} value={subproduct.subproduct_name}>
                    {subproduct.subproduct_name}
                  </MenuItem>
                ))}
            </Select>
          </Grid>
        )}

        {/* Document Upload */}
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Upload Product Document (PDF)
          </Typography>
          <Button
            variant="contained"
            component="label"
            fullWidth
            disabled={loading}
            sx={{
              bgcolor: "text.primary",
              color: "background.paper",
              "&:hover": {
                bgcolor: "text.secondary",
              },
            }}
          >
            Upload PDF
            <input
              type="file"
              accept="application/pdf"
              hidden
              onChange={handleFileUpload}
            />
          </Button>
          {uploadedFile && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              Uploaded: {uploadedFile.name}
            </Typography>
          )}
        </Grid>

        {/* Language Selection */}
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Language
          </Typography>
          <Select
            fullWidth
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            displayEmpty
            variant="outlined"
            disabled={loading}
            error={Boolean(error && !language)}
          >
            <MenuItem value="" disabled>
              Select a language
            </MenuItem>
            <MenuItem value="en">English</MenuItem>
            <MenuItem value="es">Spanish (Español)</MenuItem>
            <MenuItem value="fr">French (Français)</MenuItem>
            <MenuItem value="de">German (Deutsch)</MenuItem>
            <MenuItem value="it">Italian (Italiano)</MenuItem>
          </Select>
        </Grid>
      </Grid>

      {/* Error Message */}
      {error && (
        <Typography color="error" align="center" sx={{ mt: 2 }}>
          {error}
        </Typography>
      )}

      {/* Generate Button */}
      <Box sx={{ display: "flex", justifyContent: "center", gap: 2, mt: 4 }}>
        <Button
          variant="contained"
          onClick={handleGenerateManual}
          disabled={loading}
          sx={{
            bgcolor: "text.primary",
            color: "background.paper",
            "&:hover": {
              bgcolor: "text.secondary",
            },
          }}
        >
          {loading ? "GENERATING..." : "GENERATE USER MANUAL"}
        </Button>
      </Box>
    </Box>
  );
}