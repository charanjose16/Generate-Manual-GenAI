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
  Checkbox,
  TextField,
} from "@mui/material";
import { Inbox, Add, Description, Link, Cloud, Public } from "@mui/icons-material";
import UstLogo from "../assets/ustlogo.svg"; // Import the UST logo

export default function UserManualGenerator() {
  const [language, setLanguage] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [selectedSubProduct, setSelectedSubProduct] = useState("");
  const [uploadedFile, setUploadedFile] = useState(null);
  const [activePage, setActivePage] = useState("generateManual");
  const [selectedDataSources, setSelectedDataSources] = useState({
    uploadPDF: false,
    uploadLink: false,
    azureBlob: false,
    confluence: false,
  });
  const [pdfFile, setPdfFile] = useState(null);
  const [link, setLink] = useState("");
  const [azureBlob, setAzureBlob] = useState("");
  const [confluence, setConfluence] = useState("");

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
    if (!language.length || !selectedProduct || !uploadedFile) {
      setError("Please fill in all required fields and upload a PDF file.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("product_category", selectedProduct);
      formData.append("rag_source", uploadedFile);
      formData.append("language", language.join(",").trim()); // Handle multiple languages

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
      setLanguage([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDataSourceChange = (event) => {
    setSelectedDataSources({
      ...selectedDataSources,
      [event.target.name]: event.target.checked,
    });
  };

  const handleUploadData = () => {
    // Handle data upload logic here
    setActivePage("generateManual");
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
            <Grid item xs={12}>
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <Checkbox
                  name="uploadPDF"
                  checked={selectedDataSources.uploadPDF}
                  onChange={handleDataSourceChange}
                />
                <Typography>Upload PDF</Typography>
              </Box>
              {selectedDataSources.uploadPDF && (
                <TextField
                  fullWidth
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setPdfFile(e.target.files[0])}
                  sx={{ mt: 1 }}
                />
              )}
            </Grid>
            <Grid item xs={12}>
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <Checkbox
                  name="uploadLink"
                  checked={selectedDataSources.uploadLink}
                  onChange={handleDataSourceChange}
                />
                <Typography>Upload Link</Typography>
              </Box>
              {selectedDataSources.uploadLink && (
                <TextField
                  fullWidth
                  placeholder="Enter link"
                  value={link}
                  onChange={(e) => setLink(e.target.value)}
                  sx={{ mt: 1 }}
                />
              )}
            </Grid>
            <Grid item xs={12}>
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <Checkbox
                  name="azureBlob"
                  checked={selectedDataSources.azureBlob}
                  onChange={handleDataSourceChange}
                />
                <Typography>Azure Blob Storage</Typography>
              </Box>
              {selectedDataSources.azureBlob && (
                <TextField
                  fullWidth
                  placeholder="Enter Azure Blob Storage details"
                  value={azureBlob}
                  onChange={(e) => setAzureBlob(e.target.value)}
                  sx={{ mt: 1 }}
                />
              )}
            </Grid>
            <Grid item xs={12}>
              <Box sx={{ display: "flex", alignItems: "center" }}>
                <Checkbox
                  name="confluence"
                  checked={selectedDataSources.confluence}
                  onChange={handleDataSourceChange}
                />
                <Typography>Confluence</Typography>
              </Box>
              {selectedDataSources.confluence && (
                <TextField
                  fullWidth
                  placeholder="Enter Confluence details"
                  value={confluence}
                  onChange={(e) => setConfluence(e.target.value)}
                  sx={{ mt: 1 }}
                />
              )}
            </Grid>
          </Grid>
        </Grid>
        <Grid item xs={12}>
          <Button
            variant="contained"
            onClick={handleUploadData}
            sx={{
              bgcolor: "#2669f2",
              color: "background.paper",
              "&:hover": {
                bgcolor: "text.secondary",
              },
            }}
          >
            Upload
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
  <Box sx={{ display: "flex", flexDirection: "column" }}>
    {[
      { code: "en", name: "English" },
      { code: "es", name: "Spanish" },
      { code: "fr", name: "French" },
      { code: "de", name: "German" },
      { code: "it", name: "Italian" },
    ].map(({ code, name }) => (
      <Box sx={{ display: "flex", alignItems: "center" }} key={code}>
        <Checkbox
          checked={language.includes(code)}
          onChange={(e) => {
            if (e.target.checked) {
              setLanguage([...language, code]);
            } else {
              setLanguage(language.filter((l) => l !== code));
            }
          }}
        />
        <Typography>{name}</Typography>
      </Box>
    ))}
  </Box>
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
    <Box sx={{ display: "flex", flexDirection: "column", height: "100vh", width: "100vw", overflow: "hidden" }}>
      {/* Main Content */}
      <Box sx={{ display: "flex", flexGrow: 1, overflow: "hidden" }}>
        {/* Side Panel */}
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
            <Typography variant="h6" marginLeft="15px"> Configuration</Typography>
          </Box>
          <List>
            <ListItem
              button
              onClick={() => setActivePage("generateManual")}
              sx={{
                bgcolor: activePage === "generateManual" ? "#333" : "transparent",
                "&:hover": {
                  cursor: "pointer",
                  bgcolor: "#02062c", // Match the side panel hover color
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
                  bgcolor: "#02062c", // Match the side panel hover color
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
  
        {/* Main Content Area */}
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