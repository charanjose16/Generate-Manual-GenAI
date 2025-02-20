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
  CircularProgress,
  LinearProgress,
} from "@mui/material";
import { Add, Description } from "@mui/icons-material";
import UstLogo from "../assets/ustlogo.svg";
import axios from "axios";

export default function UserManualGenerator() {
  const [language, setLanguage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [selectedSubProduct, setSelectedSubProduct] = useState("");
  const [selectedItem, setSelectedItem] = useState("");
  const [activePage, setActivePage] = useState("generateManual");

  const [fileFormat, setFileFormat] = useState(""); // Changed to empty string initially
  const [uploadedFile, setUploadedFile] = useState(null); // State for uploaded file

  // Add new loading states
  const [loadingStates, setLoadingStates] = useState({
    searching: false,
    searchingAzure: false,
    searchingConfluence: false,
    combiningData: false,
    generatingManual: false,
  });
  const [currentLoadingStep, setCurrentLoadingStep] = useState('');

  // Add loading messages for each state
  const loadingMessages = {
    searching: "Searching product information...",
    searchingAzure: "Retrieving data from Azure Blob Storage...",
    searchingConfluence: "Searching Confluence documents...",
    combiningData: "Combining data from all sources...",
    generatingManual: "Generating your manual...",
  };

  const baseUrl = import.meta.env.VITE_BASE_URL;
  axios.defaults.headers.common['Access-Control-Allow-Origin'] = '*';

  // Fetch products data from the FastAPI backend using axios
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get(`${baseUrl}/api/products`);
        setProducts(response.data.products);
      } catch (err) {
        setError(`Failed to load products: ${err.message}`);
      }
    };
    fetchData();
  }, [baseUrl]);

  const handleProductChange = (event) => {
    const productName = event.target.value;
    setSelectedProduct(productName);
    setSelectedSubProduct("");
    setSelectedItem("");
    if (error) setError("");
  };

  const handleFAQ = async () => {
    if (!selectedItem) {
      setError("Please select a product to generate FAQ.");
      return;
    }
  
    setLoading(true);
    setError("");
  
    try {
      const formData = new FormData();
      formData.append("product_category", selectedItem);
      formData.append("language", language);
  
      const response = await axios.post(
        `${baseUrl}/generate-faq`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          responseType: "blob",
          withCredentials: false,
        }
      );
  
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `faq_${selectedItem}_${language}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
  
    } catch (err) {
      console.error('Error details:', err);
      setError('Failed to generate FAQ. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubProductChange = (event) => {
    setSelectedSubProduct(event.target.value);
    setSelectedItem("");
    if (error) setError("");
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
        const allowedTypes = {
            pdf: "application/pdf",
            document: [
                'application/msword',                                              // .doc
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'  // .docx
            ],
            text: "text/plain",
        };

        if (fileFormat === 'document') {
            if (allowedTypes.document.includes(file.type)) {
                setUploadedFile(file);
                setError("");
                return;
            }
        } else if (file.type === allowedTypes[fileFormat]) {
            setUploadedFile(file);
            setError("");
            return;
        }
        
        setError(`Please upload a valid ${fileFormat.toUpperCase()} file.`);
        setUploadedFile(null);
    }
  };

  const handleGenerateManual = async () => {
    if (!language || !selectedItem) {
      setError("Please fill in all required fields.");
      return;
    }

    // Reset all loading states
    setLoadingStates({
      searching: true,
      searchingAzure: false,
      searchingConfluence: false,
      combiningData: false,
      generatingManual: false,
    });
    setCurrentLoadingStep('searching');
    setError("");

    try {
      const formData = new FormData();
      formData.append("product_category", selectedItem);
      formData.append("language", language);

      if (uploadedFile) {
        formData.append("rag_source", uploadedFile);
      }

      // Create a sequence of loading states
      const loadingSteps = [
        'searching',
        'searchingAzure',
        'searchingConfluence',
        'combiningData',
        'generatingManual'
      ];

      // Start the loading sequence
      let currentStepIndex = 0;
      const loadingInterval = setInterval(() => {
        if (currentStepIndex < loadingSteps.length) {
          setLoadingStates(prev => ({
            ...prev,
            [loadingSteps[currentStepIndex]]: true
          }));
          setCurrentLoadingStep(loadingSteps[currentStepIndex]);
          currentStepIndex++;
        } else {
          clearInterval(loadingInterval);
        }
      }, 10000); // 20 seconds interval

      const response = await axios.post(
        `${baseUrl}/generate-manual`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          responseType: "blob",
          withCredentials: false,
        }
      );

      // Clear the interval when the response is received
      clearInterval(loadingInterval);

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `user_manual_${selectedItem}_${language}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setSelectedProduct("");
      setSelectedSubProduct("");
      setSelectedItem("");
      setLanguage("");
      setUploadedFile(null);

    } catch (err) {
      console.error('Error details:', err);
      
    } finally {
      // Reset all loading states
      setLoadingStates({
        searching: false,
        searchingAzure: false,
        searchingConfluence: false,
        combiningData: false,
        generatingManual: false,
      });
      setCurrentLoadingStep('');
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
            Select File Format
          </Typography>
          <Select
            value={fileFormat}
            onChange={(e) => setFileFormat(e.target.value)}
            displayEmpty
            variant="outlined"
            disabled={loading}
            sx={{ width: "50%" }} // Reduced width for the dropdown
          >
            <MenuItem value="" disabled>
              Select format
            </MenuItem>
            <MenuItem value="pdf">PDF</MenuItem>
            <MenuItem value="document">Document</MenuItem>
            <MenuItem value="text">Text</MenuItem>
          </Select>
        </Grid>

        {/* Only show the upload button if a file format is selected */}
        {fileFormat && (
          <Grid item xs={12}>
            <Button
              variant="outlined"
              component="label"
              disabled={loading}
              sx={{ textTransform: "none" }}
            >
              {uploadedFile ? uploadedFile.name : "Choose File"}
              <input
                type="file"
                hidden
                onChange={handleFileUpload}
                accept={
                  fileFormat === "pdf"
                    ? "application/pdf"
                    : fileFormat === "document"
                    ? "application/msword, application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    : "text/plain"
                }
              />
            </Button>
          </Grid>
        )}

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
            Save File
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

        {selectedSubProduct && (
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom>
              Items
            </Typography>
            <Select
              fullWidth
              value={selectedItem}
              onChange={(e) => setSelectedItem(e.target.value)}
              displayEmpty
              variant="outlined"
              disabled={loading}
            >
              <MenuItem value="" disabled>
                Select an item
              </MenuItem>
              {(() => {
                const product = products.find(
                  (p) => p.product_name === selectedProduct
                );
                const subProduct = product?.subproducts.find(
                  (sp) => sp.subproduct_name === selectedSubProduct
                );
                if (subProduct && subProduct.sub_subproducts) {
                  return subProduct.sub_subproducts.map((item, index) => (
                    <MenuItem key={index} value={item.sub_subproduct_name}>
                      {item.sub_subproduct_name}
                    </MenuItem>
                  ));
                }
                return null;
              })()}
            </Select>
          </Grid>
        )}

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
          onClick={handleFAQ}
          disabled={loading}
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

  // Add LoadingOverlay component
  const LoadingOverlay = () => {
    const isLoading = Object.values(loadingStates).some(state => state);
    
    if (!isLoading) return null;

    return (
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
        }}
      >
        <Box
          sx={{
            bgcolor: 'background.paper',
            borderRadius: 2,
            p: 4,
            maxWidth: 400,
            width: '90%',
            textAlign: 'center',
          }}
        >
          <Box sx={{ position: 'relative', display: 'inline-flex' }}>
            <CircularProgress
              size={68}
              sx={{
                color: '#2669f2',
                animationDuration: '550ms',
              }}
            />
            <Box
              sx={{
                top: 0,
                left: 0,
                bottom: 0,
                right: 0,
                position: 'absolute',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography
                variant="caption"
                component="div"
                color="text.secondary"
              >
                {Math.round(
                  (Object.values(loadingStates).filter(Boolean).length /
                    Object.values(loadingStates).length) *
                    100
                )}%
              </Typography>
            </Box>
          </Box>
          <Typography variant="h6" sx={{ mt: 2, mb: 1 }}>
            {loadingMessages[currentLoadingStep]}
          </Typography>
          <Box sx={{ width: '100%', mt: 2 }}>
            <LinearProgress
              variant="determinate"
              value={
                (Object.values(loadingStates).filter(Boolean).length /
                  Object.values(loadingStates).length) *
                100
              }
              sx={{
                height: 8,
                borderRadius: 4,
                backgroundColor: 'rgba(38, 105, 242, 0.2)',
                '& .MuiLinearProgress-bar': {
                  backgroundColor: '#2669f2',
                },
              }}
            />
          </Box>
        </Box>
      </Box>
    );
  };

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
      <LoadingOverlay />
    </Box>
  );
}