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
import PropTypes from 'prop-types';

// Add these flag SVG components at the top of the file
const countryFlags = {
  en: (
    <svg className="w-5 h-5" viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg">
      <rect width="640" height="480" fill="#012169"/>
      <path d="M75,0l244,181L562,0h78v62L400,241l240,178v61h-80L320,301L81,480H0v-60L239,241L0,62V0H75z" fill="#FFF"/>
      <path d="M424,281l216,159v40L369,281h55z M240,301l6,4L54,480H0L240,301z M640,0v3L391,191l2-44L590,0H640z M0,0l239,176h-60L0,42V0z" fill="#C8102E"/>
      <path d="M241,0v480h160V0H241zM0,160v160h640V160H0z" fill="#FFF"/>
      <path d="M0,193v96h640v-96H0zM273,0v480h96V0H273z" fill="#C8102E"/>
    </svg>
  ),
  es: (
    <svg className="w-5 h-5" viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg">
      <path fill="#AA151B" d="M0 0h640v480H0z"/>
      <path fill="#F1BF00" d="M0 120h640v240H0z"/>
    </svg>
  ),
  fr: (
    <svg className="w-5 h-5" viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg">
      <path fill="#ED2939" d="M0 0h640v480H0z"/>
      <path fill="#FFF" d="M0 0h426.7v480H0z"/>
      <path fill="#002395" d="M0 0h213.3v480H0z"/>
    </svg>
  ),
  de: (
    <svg className="w-5 h-5" viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg">
      <path fill="#FFCE00" d="M0 320h640v160H0z"/>
      <path d="M0 0h640v160H0z"/>
      <path fill="#D00" d="M0 160h640v160H0z"/>
    </svg>
  ),
  it: (
    <svg className="w-5 h-5" viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg">
      <path fill="#009246" d="M0 0h213.3v480H0z"/>
      <path fill="#FFF" d="M213.3 0h213.4v480H213.3z"/>
      <path fill="#CE2B37" d="M426.7 0H640v480H426.7z"/>
    </svg>
  ),
};

// Define PDFPreviewModal as a separate component before the main component
function PDFPreviewModal({ pdfUrl, onClose, selectedItem, language }) {
  if (!pdfUrl) return null;
  
  const handleDownload = () => {
    const link = document.createElement('a');
    link.href = pdfUrl;
    link.download = `FAQ_${selectedItem}_${language}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 pl-80">
      <div className="bg-white rounded-lg p-4 w-11/12 h-5/6 max-w-6xl flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">FAQ Preview</h2>
          <div className="flex gap-2">
            <button
              onClick={handleDownload}
              className="bg-teal-500 text-black px-4 py-2 rounded hover:bg-teal-600 flex items-center gap-2"
            >
              Download
            </button>
            <button
              onClick={onClose}
              className="bg-gray-300 text-gray-700 px-4 py-2 rounded hover:bg-gray-400"
            >
              Close
            </button>
          </div>
        </div>
        <div className="flex-grow bg-gray-100 rounded">
          <iframe
            src={pdfUrl}
            className="w-full h-full rounded"
            title="PDF Preview"
          />
        </div>
      </div>
    </div>
  );
}

// Update PropTypes to include the new props
PDFPreviewModal.propTypes = {
  pdfUrl: PropTypes.string,
  onClose: PropTypes.func.isRequired,
  selectedItem: PropTypes.string.isRequired,
  language: PropTypes.string.isRequired
};

export default function UserManualGenerator() {
  const [language, setLanguage] = useState("");
  const [loading, ] = useState(false);
  const [error, setError] = useState("");
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [selectedSubProduct, setSelectedSubProduct] = useState("");
  const [selectedItem, setSelectedItem] = useState("");
  const [activePage, setActivePage] = useState("generateManual");

  const [fileFormat, setFileFormat] = useState("");
  const [uploadedFile, setUploadedFile] = useState(null);

  // Add FAQ-specific loading states and messages
  const [loadingStates, setLoadingStates] = useState({
    searching: false,
    searchingAzure: false,
    searchingConfluence: false,
    combiningData: false,
    generatingManual: false,
    searchingFAQ: false,
    analyzingQuestions: false,
    generatingAnswers: false,
    formattingFAQ: false,
    finalizingDocument: false,
  });

  const [currentLoadingStep, setCurrentLoadingStep] = useState('');

  // Separate loading messages for FAQ
  const faqLoadingMessages = {
    searchingFAQ: "Searching product information...",
    analyzingQuestions: "Analyzing frequently asked questions...",
    generatingAnswers: "Generating comprehensive answers...",
    formattingFAQ: "Formatting FAQ document...",
    finalizingDocument: "Finalizing your FAQ document..."
  };

  // Add manual generation loading messages
  const manualLoadingMessages = {
    searching: "Searching product information...",
    searchingAzure: "Retrieving data from Azure Blob Storage...",
    searchingConfluence: "Searching Confluence documents...",
    combiningData: "Combining data from all sources...",
    generatingManual: "Generating your manual..."
  };

  const baseUrl = import.meta.env.VITE_BASE_URL;
  axios.defaults.headers.common['Access-Control-Allow-Origin'] = '*';

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

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
        const allowedTypes = {
            pdf: "application/pdf",
            document: [
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
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

  const handleProductChange = (event) => {
    const productName = event.target.value;
    setSelectedProduct(productName);
    setSelectedSubProduct("");
    setSelectedItem("");
    if (error) setError("");
  };

  const handleSubProductChange = (event) => {
    setSelectedSubProduct(event.target.value);
    setSelectedItem("");
    if (error) setError("");
  };

  const handleGenerateManual = async () => {
    if (!language || !selectedItem) {
      setError("Please fill in all required fields.");
      return;
    }

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

      const loadingSteps = [
        'searching',
        'searchingAzure',
        'searchingConfluence',
        'combiningData',
        'generatingManual'
      ];

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
      }, 12000);

      const response = await axios.post(
        `${baseUrl}/api/generate-manual`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          responseType: "blob",
        }
      );

      clearInterval(loadingInterval);

      // Direct download for manual PDF
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Manual_${selectedItem}_${language}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

    } catch (err) {
      console.error("Error generating manual:", err);
      setError(err.response?.data?.detail || "Failed to generate manual");
    } finally {
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

  // Add these new state variables at the top
  const [showPreview, setShowPreview] = useState(false);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [, setPdfBlob] = useState(null);


  // Add the cleanup function
  const handleClosePreview = () => {
    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl);
    }
    setShowPreview(false);
    setPdfUrl(null);
    setPdfBlob(null);
  };

  // Update handleFAQ function to handle base64 PDF data
  const handleFAQ = async () => {
    if (!language || !selectedItem) {
      setError("Please fill in all required fields.");
      return;
    }

    setLoadingStates({
      ...loadingStates,
      searchingFAQ: true,
    });
    setCurrentLoadingStep('searchingFAQ');
    setError("");

    try {
      const formData = new FormData();
      formData.append("product_category", selectedItem);
      formData.append("language", language);

      const faqSteps = [
        'searchingFAQ',
        'analyzingQuestions',
        'generatingAnswers',
        'formattingFAQ',
        'finalizingDocument'
      ];

      let currentStepIndex = 0;
      const loadingInterval = setInterval(() => {
        if (currentStepIndex < faqSteps.length) {
          setLoadingStates(prev => ({
            ...prev,
            [faqSteps[currentStepIndex]]: true
          }));
          setCurrentLoadingStep(faqSteps[currentStepIndex]);
          currentStepIndex++;
        } else {
          clearInterval(loadingInterval);
        }
      }, 10000);

      const response = await axios.post(
        `${baseUrl}/api/generate-faq`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );

      clearInterval(loadingInterval);

      // Show preview for FAQ PDF
      if (response.data && response.data.pdf_base64) {
        const byteCharacters = atob(response.data.pdf_base64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'application/pdf' });
        
        const url = URL.createObjectURL(blob);
        setPdfUrl(url);
        setShowPreview(true);
      } else {
        throw new Error('Invalid PDF data received');
      }

    } catch (err) {
      console.error("Error generating FAQ:", err);
      setError(err.response?.data?.detail || "Failed to generate FAQ");
    } finally {
      setLoadingStates({
        ...loadingStates,
        searchingFAQ: false,
        analyzingQuestions: false,
        generatingAnswers: false,
        formattingFAQ: false,
        finalizingDocument: false,
      });
      setCurrentLoadingStep('');
    }
  };

  const renderAddDataSourcePage = () => (
    <Box sx={{ p: 4,pl:20, width: "100%", height: "100%" }}>
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
            sx={{ width: "50%" }}
          >
            <MenuItem value="" disabled>
              Select format
            </MenuItem>
            <MenuItem value="pdf">PDF</MenuItem>
            <MenuItem value="document">Document</MenuItem>
            <MenuItem value="text">Text</MenuItem>
          </Select>
        </Grid>

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
              bgcolor: "#0d9488",
              color: "background.paper",
              "&:hover": {
                bgcolor: "green",
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
    <Box sx={{ p: 4,pl:20, width: "100%", height: "100%" }}>
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
            <MenuItem value="en" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {countryFlags.en}
              English
            </MenuItem>
            <MenuItem value="es" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {countryFlags.es}
              Spanish
            </MenuItem>
            <MenuItem value="fr" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {countryFlags.fr}
              French
            </MenuItem>
            <MenuItem value="de" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {countryFlags.de}
              German
            </MenuItem>
            <MenuItem value="it" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {countryFlags.it}
              Italian
            </MenuItem>
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
            bgcolor: "#0d9488",
            color: "background.paper",
            "&:hover": {
              bgcolor: "green",
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

  // Update LoadingOverlay component
  const LoadingOverlay = () => {
    const isLoading = Object.values(loadingStates).some(state => state);
    
    if (!isLoading) return null;

    // Determine which loading messages to use based on current step
    const currentMessages = currentLoadingStep.includes('FAQ') ? faqLoadingMessages : manualLoadingMessages;

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
            {currentMessages[currentLoadingStep]}
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
              width: 340,
              boxSizing: "border-box",
              bgcolor: "#0d9488",
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
                bgcolor: activePage === "generateManual" ? "#065F46" : "transparent",
                "&:hover": {
                  cursor: "pointer",
                  bgcolor: "#34D399",
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
                bgcolor: activePage === "addDataSource" ? "#065F46" : "transparent",
                "&:hover": {
                  cursor: "pointer",
                  bgcolor: "#34D399",
                  
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
      {showPreview && (
        <PDFPreviewModal
          pdfUrl={pdfUrl}
          onClose={handleClosePreview}
          selectedItem={selectedItem}
          language={language}
        />
      )}
    </Box>
  );
}