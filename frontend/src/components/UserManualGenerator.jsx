import { useState } from "react";
import { 
  TextField, 
  Select, 
  MenuItem, 
  Button, 
  Grid, 
  Box, 
  Typography 
} from "@mui/material";

export default function UserManualGenerator() {
  const [link, setLink] = useState("");
  const [product, setProduct] = useState("");
  const [language, setLanguage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showSuccess, setShowSuccess] = useState(false);

  const handleLinkChange = (event) => {
    setLink(event.target.value);
    if (error) setError("");
  };

  const handleProductChange = (event) => {
    setProduct(event.target.value);
    if (error) setError("");
  };

  const handleLanguageChange = (event) => {
    setLanguage(event.target.value);
    if (error) setError("");
  };

  const validateUrl = (url) => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  const handleGenerateManual = async () => {
    if (!link || !language) {
      setError("Please fill in all required fields");
      return;
    }

    if (!validateUrl(link)) {
      setError("Please enter a valid URL");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const trimmedLink = link.trim();
      const formattedLink = trimmedLink.startsWith('http') ? trimmedLink : `https://${trimmedLink}`;
      
      const payload = {
        website_link: formattedLink,
        product: product.trim(),
        language: language.trim(),
      };

      const response = await fetch("http://localhost:8000/generate-manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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

      setShowSuccess(true);
      setLink("");
      setProduct("");
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
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Link
          </Typography>
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Enter link here"
            value={link}
            onChange={handleLinkChange}
            disabled={loading}
            error={Boolean(error && !link)}
          />
        </Grid>
        
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Product
          </Typography>
          <Select
            fullWidth
            value={product}
            onChange={handleProductChange}
            displayEmpty
            variant="outlined"
            disabled={loading}
          >
            <MenuItem value="" disabled>
              Select a product 
            </MenuItem>
            <MenuItem value="product1">Product 1</MenuItem>
            <MenuItem value="product2">Product 2</MenuItem>
            <MenuItem value="product3">Product 3</MenuItem>
          </Select>
        </Grid>
        
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Language
          </Typography>
          <Select
            fullWidth
            value={language}
            onChange={handleLanguageChange}
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

      {error && (
        <Typography color="error" align="center" sx={{ mt: 2 }}>
          {error}
        </Typography>
      )}

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
        <Button
          variant="outlined"
          sx={{
            color: "text.primary",
            borderColor: "text.primary",
            "&:hover": {
              bgcolor: "action.hover",
              borderColor: "text.secondary",
            },
          }}
        >
          FAQ
        </Button>
      </Box>
    </Box>
  );
}
