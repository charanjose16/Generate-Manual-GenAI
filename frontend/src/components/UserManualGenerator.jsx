import { useState, useEffect } from "react";
import {
  Select,
  MenuItem,
  Button,
  Grid,
  Box,
  Typography,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  TextField,
} from "@mui/material";
import { Add, Description } from "@mui/icons-material";
import UstLogo from "../assets/ustlogo.svg";

export default function UserManualGenerator() {
  const [language, setLanguage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [selectedSubProduct, setSelectedSubProduct] = useState("");
  const [activePage, setActivePage] = useState("generateManual");

  // Data source states
  const [dataSources, setDataSources] = useState({
    pdf: {
      enabled: false,
      file: null,
      fileName: ""
    },
    link: {
      enabled: false,
      value: ""
    },
    azureBlob: {
      enabled: false,
      value: ""
    },
    confluence: {
      enabled: false,
      value: ""
    }
  });

  // Fetch products data from the FastAPI backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/products");
        if (!response.ok) {
          throw new Error("Failed to fetch products");
        }
        const data = await response.json();
        setProducts(data.products);
      } catch (err) {
        setError(`Failed to load products: ${err.message}`);
      }
    };
    fetchData();
  }, []);

  const handleProductChange = (event) => {
    const productName = event.target.value;
    setSelectedProduct(productName);
    setSelectedSubProduct("");
    if (error) setError("");
  };

  const handleSubProductChange = (event) => {
    setSelectedSubProduct(event.target.value);
    if (error) setError("");
  };

  const handleDataSourceToggle = (sourceType) => {
    setDataSources(prev => ({
      ...prev,
      [sourceType]: {
        ...prev[sourceType],
        enabled: !prev[sourceType].enabled
      }
    }));
  };

  const handleDataSourceValueChange = (sourceType, value) => {
    setDataSources(prev => ({
      ...prev,
      [sourceType]: {
        ...prev[sourceType],
        value: value
      }
    }));
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file && file.type === "application/pdf") {
      setDataSources(prev => ({
        ...prev,
        pdf: {
          ...prev.pdf,
          file: file,
          fileName: file.name
        }
      }));
      setError("");
    } else {
      setError("Please upload a valid PDF file.");
      setDataSources(prev => ({
        ...prev,
        pdf: {
          ...prev.pdf,
          file: null,
          fileName: ""
        }
      }));
    }
  };

  const handleGenerateManual = async () => {
    if (!language || !selectedProduct) {
      setError("Please fill in all required fields.");
      return;
    }

    if (!Object.values(dataSources).some(source => source.enabled)) {
      setError("Please select at least one data source.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("product_category", selectedProduct);
      formData.append("language", language);

      // Append data sources based on what's enabled
      if (dataSources.pdf.enabled && dataSources.pdf.file) {
        formData.append("rag_source", dataSources.pdf.file);
      }
      if (dataSources.link.enabled) {
        formData.append("link_source", dataSources.link.value);
      }
      if (dataSources.azureBlob.enabled) {
        formData.append("azure_source", dataSources.azureBlob.value);
      }
      if (dataSources.confluence.enabled) {
        formData.append("confluence_source", dataSources.confluence.value);
      }

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
      a.download = `user_manual_${selectedProduct}_${language}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      // Reset form fields after successful generation
      setSelectedProduct("");
      setSelectedSubProduct("");
      setLanguage("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const renderAddDataSourcePage = () => (
    <Box sx={{ p: 4, width: "100%", height: "100%" }}>
      <Typography variant="h5" gutterBottom>
        Add Data Source
      </Typography>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            Select Data Sources
          </Typography>
          <Grid container spacing={2}>
            {/* PDF Upload Section */}
            <Grid item xs={12}>
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={dataSources.pdf.enabled}
                  onChange={() => handleDataSourceToggle('pdf')}
                  style={{ marginRight: 8 }}
                />
                <Typography>Upload PDF</Typography>
              </Box>
              {dataSources.pdf.enabled && (
                <Box sx={{ mt: 1 }}>
                  <Button
                    variant="outlined"
                    component="label"
                    disabled={loading}
                    sx={{ textTransform: "none" }}
                  >
                    {dataSources.pdf.fileName || "Choose PDF"}
                    <input
                      type="file"
                      accept="application/pdf"
                      hidden
                      onChange={handleFileUpload}
                    />
                  </Button>
                  {dataSources.pdf.fileName && (
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {dataSources.pdf.fileName}
                    </Typography>
                  )}
                </Box>
              )}
            </Grid>

            {/* Link Upload Section */}
            <Grid item xs={12}>
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={dataSources.link.enabled}
                  onChange={() => handleDataSourceToggle('link')}
                  style={{ marginRight: 8 }}
                />
                <Typography>Upload Link</Typography>
              </Box>
              {dataSources.link.enabled && (
                <TextField
                  fullWidth
                  placeholder="Enter link"
                  value={dataSources.link.value}
                  onChange={(e) => handleDataSourceValueChange('link', e.target.value)}
                  sx={{ mt: 1 }}
                />
              )}
            </Grid>

            {/* Azure Blob Section */}
            <Grid item xs={12}>
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={dataSources.azureBlob.enabled}
                  onChange={() => handleDataSourceToggle('azureBlob')}
                  style={{ marginRight: 8 }}
                />
                <Typography>Azure Blob Storage</Typography>
              </Box>
              {dataSources.azureBlob.enabled && (
                <TextField
                  fullWidth
                  placeholder="Enter Azure Blob Storage details"
                  value={dataSources.azureBlob.value}
                  onChange={(e) => handleDataSourceValueChange('azureBlob', e.target.value)}
                  sx={{ mt: 1 }}
                />
              )}
            </Grid>

            {/* Confluence Section */}
            <Grid item xs={12}>
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={dataSources.confluence.enabled}
                  onChange={() => handleDataSourceToggle('confluence')}
                  style={{ marginRight: 8 }}
                />
                <Typography>Confluence</Typography>
              </Box>
              {dataSources.confluence.enabled && (
                <TextField
                  fullWidth
                  placeholder="Enter Confluence details"
                  value={dataSources.confluence.value}
                  onChange={(e) => handleDataSourceValueChange('confluence', e.target.value)}
                  sx={{ mt: 1 }}
                />
              )}
            </Grid>
          </Grid>
        </Grid>

        {error && (
          <Grid item xs={12}>
            <Typography color="error">{error}</Typography>
          </Grid>
        )}

        <Grid item xs={12}>
          <Button
            variant="contained"
            onClick={() => setActivePage("generateManual")}
            sx={{
              bgcolor: "#2669f2",
              color: "background.paper",
              "&:hover": {
                bgcolor: "text.secondary",
              },
            }}
          >
            Save Data Sources
          </Button>
        </Grid>
      </Grid>
    </Box>
  );

  const renderGenerateManualPage = () => (
    <Box sx={{ p: 4, width: "100%", height: "100%" }}>
      <Typography variant="h5" gutterBottom>
        Generate User Manual
      </Typography>
      <Grid container spacing={3} sx={{ maxWidth: 800 }}>
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
          >
            <MenuItem value="" disabled>
              Select a language
            </MenuItem>
            <MenuItem value="en">English</MenuItem>
            <MenuItem value="es">Spanish</MenuItem>
            <MenuItem value="fr">French</MenuItem>
            <MenuItem value="de">German</MenuItem>
            <MenuItem value="it">Italian</MenuItem>
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
            bgcolor: "#2669f2",
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
              borderColor: "text.secondary",
            },
          }}
        >
          FAQ
        </Button>
      </Box>
    </Box>
  );

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        width: "100vw",
        overflow: "hidden",
      }}
    >
      <Box sx={{ display: "flex", flexGrow: 1, overflow: "hidden" }}>
        <Drawer
          variant="permanent"
          sx={{
            width: 240,
            flexShrink: 0,
            "& .MuiDrawer-paper": {
              width: 240,
              boxSizing: "border-box",
              bgcolor: "#02062c",
              color: "#fff",
            },
          }}
        >
          <Box sx={{ p: 2, display: "flex", alignItems: "center", gap: 1 }}>
            <img src={UstLogo} alt="UST Logo" style={{ width: 24, height: 24 }} />
            <Typography variant="h6" marginLeft="15px">
              Configuration
            </Typography>
          </Box>
          <List>
            <ListItem
              button
              onClick={() => setActivePage("generateManual")}
              sx={{
                bgcolor: activePage === "generateManual" ? "#333" : "transparent",
                "&:hover": {
                  cursor: "pointer",
                  bgcolor: "#02062c",
                },
              }}
            >
              <ListItemIcon>
                <Description sx={{ color: "#fff" }} />
              </ListItemIcon>
              <ListItemText primary="Generate Manual" />
            </ListItem>
            <ListItem
              button
              onClick={() => setActivePage("addDataSource")}
              sx={{
                bgcolor: activePage === "addDataSource" ? "#333" : "transparent",
                "&:hover": {
                  cursor: "pointer",
                  bgcolor: "#02062c",
                },
              }}
            >
              <ListItemIcon>
                <Add sx={{ color: "#fff" }} />
              </ListItemIcon>
              <ListItemText primary="Add Data Source" />
            </ListItem>
          </List>
        </Drawer>

        <Box
          sx={{
            flexGrow: 1,
            bgcolor: "background.paper",
            overflow: "auto",
            p: 3,
            height: "100%",
          }}
        >
          {activePage === "generateManual"
            ? renderGenerateManualPage()
            : renderAddDataSourcePage()}
        </Box>
      </Box>
    </Box>
  );
}