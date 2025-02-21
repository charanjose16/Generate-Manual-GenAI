import { useState, useEffect, Fragment } from "react";
import { Listbox, Transition } from "@headlessui/react";
import axios from "axios";

// Inline SVG icons for country flags
const countryIcons = {
  en: (
    <svg
      className="w-5 h-5 inline-block mr-1"
      viewBox="0 0 60 40"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Simplified Union Jack */}
      <rect width="60" height="40" fill="#012169" />
      <path d="M0,0 L60,40 M60,0 L0,40" stroke="#fff" strokeWidth="8" />
      <path d="M0,0 L60,40 M60,0 L0,40" stroke="#cf142b" strokeWidth="4" />
    </svg>
  ),
  es: (
    <svg
      className="w-5 h-5 inline-block mr-1"
      viewBox="0 0 640 480"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Simplified Spanish Flag */}
      <rect width="640" height="480" fill="#aa151b" />
      <rect y="160" width="640" height="160" fill="#f1bf00" />
    </svg>
  ),
  fr: (
    <svg
      className="w-5 h-5 inline-block mr-1"
      viewBox="0 0 3 2"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* French Tricolour */}
      <rect width="1" height="2" fill="#0055A4" />
      <rect x="1" width="1" height="2" fill="#fff" />
      <rect x="2" width="1" height="2" fill="#EF4135" />
    </svg>
  ),
  de: (
    <svg
      className="w-5 h-5 inline-block mr-1"
      viewBox="0 0 5 3"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* German Flag */}
      <rect width="5" height="1" y="0" fill="#000" />
      <rect width="5" height="1" y="1" fill="#D00" />
      <rect width="5" height="1" y="2" fill="#FFCE00" />
    </svg>
  ),
  it: (
    <svg
      className="w-5 h-5 inline-block mr-1"
      viewBox="0 0 3 2"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Italian Tricolour */}
      <rect width="1" height="2" fill="#009246" />
      <rect x="1" width="1" height="2" fill="#fff" />
      <rect x="2" width="1" height="2" fill="#CE2B37" />
    </svg>
  ),
};

// Language options with full names and corresponding codes
const languages = [
  { code: "en", name: "English" },
  { code: "es", name: "Spanish" },
  { code: "fr", name: "French" },
  { code: "de", name: "German" },
  { code: "it", name: "Italian" },
];

// Add FAQ loading messages at the top with other constants
const faqLoadingMessages = {
  searchingProduct: "Searching product information...",
  generatingQuestions: "Generating relevant questions...",
  creatingAnswers: "Creating comprehensive answers...",
  formattingContent: "Formatting FAQ content...",
  generatingPDF: "Generating FAQ document..."
};

// Add manual generation loading messages at the top with other constants
const manualLoadingMessages = {
  searchingProduct: "Searching product information...",
  analyzingContent: "Analyzing product content...",
  generatingContent: "Generating manual content...",
  formattingManual: "Formatting manual document...",
  finalizingDocument: "Finalizing your manual..."
};

export default function UserManualGenerator() {
  const [language, setLanguage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [selectedSubProduct, setSelectedSubProduct] = useState("");
  const [selectedItem, setSelectedItem] = useState("");
  const [activePage, setActivePage] = useState("generateManual");

  const baseUrl = import.meta.env.VITE_BASE_URL;

  const [dataSources, setDataSources] = useState({
    pdf: { enabled: false, file: null, fileName: "" },
    link: { enabled: false, value: "" },
    azureBlob: { enabled: false, value: "" },
    confluence: { enabled: false, value: "" },
  });

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

  const loadingMessages = {
    searching: "Searching product information...",
    searchingAzure: "Retrieving data from Azure Blob Storage...",
    searchingConfluence: "Searching Confluence documents...",
    combiningData: "Combining data from all sources...",
    generatingManual: "Generating your manual...",
    searchingFAQ: "Searching common questions...",
    analyzingQuestions: "Analyzing frequently asked questions...",
    generatingAnswers: "Generating comprehensive answers...",
    formattingFAQ: "Formatting FAQ document...",
    finalizingDocument: "Finalizing your FAQ document...",
  };

  const [loadingFAQ, setLoadingFAQ] = useState(false);

  // Add state for FAQ loading step
  const [currentFAQStep, setCurrentFAQStep] = useState('');

  // Add new states for PDF preview
  const [showPreview, setShowPreview] = useState(false);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [pdfBlob, setPdfBlob] = useState(null);

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

  const handleProductChange = (value) => {
    setSelectedProduct(value);
    setSelectedSubProduct("");
    setSelectedItem("");
    if (error) setError("");
  };

  const handleSubProductChange = (value) => {
    setSelectedSubProduct(value);
    setSelectedItem("");
    if (error) setError("");
  };

  const handleDataSourceToggle = (sourceType) => {
    setDataSources((prev) => ({
      ...prev,
      [sourceType]: {
        ...prev[sourceType],
        enabled: !prev[sourceType].enabled,
      },
    }));
  };

  const handleDataSourceValueChange = (sourceType, value) => {
    setDataSources((prev) => ({
      ...prev,
      [sourceType]: {
        ...prev[sourceType],
        value: value,
      },
    }));
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file && file.type === "application/pdf") {
      setDataSources((prev) => ({
        ...prev,
        pdf: {
          ...prev.pdf,
          file: file,
          fileName: file.name,
        },
      }));
      setError("");
    } else {
      setError("Please upload a valid PDF file.");
      setDataSources((prev) => ({
        ...prev,
        pdf: { ...prev.pdf, file: null, fileName: "" },
      }));
    }
  };

  const handleFAQ = async () => {
    if (!language || !selectedItem) {
      setError("Please fill in all required fields.");
      return;
    }

    setError("");
    setLoadingFAQ(true);
    setCurrentFAQStep('searchingProduct');

    try {
      const formData = new FormData();
      formData.append("product_category", selectedItem);
      formData.append("language", language);
      formData.append("preview", "true");

      // Update FAQ loading steps
      const steps = ['searchingProduct', 'generatingQuestions', 'creatingAnswers', 'formattingContent', 'generatingPDF'];
      for (let i = 0; i < steps.length; i++) {
        setCurrentFAQStep(steps[i]);
        await new Promise(resolve => setTimeout(resolve, 10000));
      }

      const response = await axios.post(`${baseUrl}/api/generate-faq`, formData);

      // Handle the PDF data from response
      if (response.data && response.data.pdf_base64) {
        // Convert base64 to blob
        const byteCharacters = atob(response.data.pdf_base64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'application/pdf' });
        
        // Create URL for preview
        const url = URL.createObjectURL(blob);
        setPdfBlob(blob);
        setPdfUrl(url);
        setShowPreview(true);
      } else {
        throw new Error('Invalid PDF data received');
      }

    } catch (err) {
      console.error("Error generating FAQ:", err);
      setError(err.response?.data?.detail || "Failed to generate FAQ");
    } finally {
      setLoadingFAQ(false);
      setCurrentFAQStep('');
    }
  };

  const handleGenerateManual = async () => {
    if (!language || !selectedItem) {
      setError("Please fill in all required fields.");
      return;
    }

    setError("");
    setLoading(true);
    
    try {
      const formData = new FormData();
      formData.append("product_category", selectedItem);
      formData.append("language", language);

      // Update manual generation loading steps
      const steps = ['searchingProduct', 'analyzingContent', 'generatingContent', 'formattingManual', 'finalizingDocument'];
      for (let i = 0; i < steps.length; i++) {
        setCurrentLoadingStep(steps[i]);
        await new Promise(resolve => setTimeout(resolve, 12000));
      }

      const response = await axios.post(
        `${baseUrl}/api/generate-manual`,
        formData,
        { responseType: "blob" }
      );

      const blob = new Blob([response.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `manual_${selectedItem}_${language}.pdf`;
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(link);
    } catch (err) {
      console.error("Error generating manual:", err);
      setError(err.response?.data?.detail || "Failed to generate manual");
    } finally {
      setLoading(false);
      setCurrentLoadingStep('');
    }
  };

  const renderGenerateManualPage = () => (
    <div className="p-4 w-full">
      <h2 className="text-xl font-semibold mb-4">Generate User Manual</h2>
      <div className="grid grid-cols-1 gap-4 max-w-2xl relative">
        {/* Product Listbox */}
        <div className="relative">
          <label className="block mb-1">Product</label>
          <Listbox value={selectedProduct} onChange={handleProductChange}>
            {({ open }) => (
              <>
                <Listbox.Button className="relative w-full py-2 pl-3 pr-10 text-left bg-white border border-gray-300 rounded-md shadow-sm cursor-default focus:outline-none">
                  <span className="block truncate">
                    {selectedProduct || "Select a product"}
                  </span>
                </Listbox.Button>
                <Transition
                  show={open}
                  as={Fragment}
                  leave="transition ease-in duration-100"
                  leaveFrom="opacity-100"
                  leaveTo="opacity-0"
                >
                  <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                    {products.map((product, index) => (
                      <Listbox.Option key={index} value={product.product_name}>
                        {({ active }) => (
                          <span
                            className={`block cursor-pointer select-none py-2 pl-3 pr-10 ${
                              active ? "bg-teal-500 text-white" : "text-gray-900"
                            }`}
                          >
                            {product.product_name}
                          </span>
                        )}
                      </Listbox.Option>
                    ))}
                  </Listbox.Options>
                </Transition>
              </>
            )}
          </Listbox>
        </div>

        {/* Sub-Product Listbox */}
        {selectedProduct && (
          <div className="relative">
            <label className="block mb-1">Sub-Product</label>
            <Listbox value={selectedSubProduct} onChange={handleSubProductChange}>
              {({ open }) => (
                <>
                  <Listbox.Button className="relative w-full py-2 pl-3 pr-10 text-left bg-white border border-gray-300 rounded-md shadow-sm cursor-default focus:outline-none">
                    <span className="block truncate">
                      {selectedSubProduct || "Select a sub-product"}
                    </span>
                  </Listbox.Button>
                  <Transition
                    show={open}
                    as={Fragment}
                    leave="transition ease-in duration-100"
                    leaveFrom="opacity-100"
                    leaveTo="opacity-0"
                  >
                    <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                      {(() => {
                        const product = products.find(
                          (p) => p.product_name === selectedProduct
                        );
                        return product?.subproducts.map((subproduct, index) => (
                          <Listbox.Option
                            key={index}
                            value={subproduct.subproduct_name}
                          >
                            {({ active }) => (
                              <span
                                className={`block cursor-pointer select-none py-2 pl-3 pr-10 ${
                                  active ? "bg-teal-500 text-white" : "text-gray-900"
                                }`}
                              >
                                {subproduct.subproduct_name}
                              </span>
                            )}
                          </Listbox.Option>
                        ));
                      })()}
                    </Listbox.Options>
                  </Transition>
                </>
              )}
            </Listbox>
          </div>
        )}

        {/* Items Listbox */}
        {selectedSubProduct && (
          <div className="relative">
            <label className="block mb-1">Items</label>
            <Listbox value={selectedItem} onChange={setSelectedItem}>
              {({ open }) => (
                <>
                  <Listbox.Button className="relative w-full py-2 pl-3 pr-10 text-left bg-white border border-gray-300 rounded-md shadow-sm cursor-default focus:outline-none">
                    <span className="block truncate">
                      {selectedItem || "Select an item"}
                    </span>
                  </Listbox.Button>
                  <Transition
                    show={open}
                    as={Fragment}
                    leave="transition ease-in duration-100"
                    leaveFrom="opacity-100"
                    leaveTo="opacity-0"
                  >
                    <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                      {(() => {
                        const product = products.find(
                          (p) => p.product_name === selectedProduct
                        );
                        const subProduct = product?.subproducts.find(
                          (sp) => sp.subproduct_name === selectedSubProduct
                        );
                        return subProduct?.sub_subproducts?.map((item, index) => (
                          <Listbox.Option
                            key={index}
                            value={item.sub_subproduct_name}
                          >
                            {({ active }) => (
                              <span
                                className={`block cursor-pointer select-none py-2 pl-3 pr-10 ${
                                  active ? "bg-teal-500 text-white" : "text-gray-900"
                                }`}
                              >
                                {item.sub_subproduct_name}
                              </span>
                            )}
                          </Listbox.Option>
                        ));
                      })()}
                    </Listbox.Options>
                  </Transition>
                </>
              )}
            </Listbox>
          </div>
        )}

        {/* Language Listbox with Country Icons */}
        <div className="relative">
          <label className="block mb-1">Language</label>
          <Listbox value={language} onChange={setLanguage}>
            {({ open }) => (
              <>
                <Listbox.Button className="relative w-full py-2 pl-3 pr-10 text-left bg-white border border-gray-300 rounded-md shadow-sm cursor-default focus:outline-none">
                  <span className="block truncate">
                    {language
                      ? (() => {
                          const selected = languages.find(
                            (l) => l.code === language
                          );
                          return (
                            <>
                              {countryIcons[language]}
                              {selected.name}
                            </>
                          );
                        })()
                      : "Select a language"}
                  </span>
                </Listbox.Button>
                <Transition
                  show={open}
                  as={Fragment}
                  leave="transition ease-in duration-100"
                  leaveFrom="opacity-100"
                  leaveTo="opacity-0"
                >
                  <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                    {languages.map((lang) => (
                      <Listbox.Option key={lang.code} value={lang.code}>
                        {({ active }) => (
                          <span
                            className={`block cursor-pointer select-none py-2 pl-3 pr-10 ${
                              active ? "bg-teal-500 text-white" : "text-gray-900"
                            }`}
                          >
                            {countryIcons[lang.code]}
                            {lang.name}
                          </span>
                        )}
                      </Listbox.Option>
                    ))}
                  </Listbox.Options>
                </Transition>
              </>
            )}
          </Listbox>
        </div>

        {error && <p className="text-red-500">{error}</p>}

        <div className="flex space-x-4">
          <button
            onClick={handleGenerateManual}
            disabled={loading || loadingFAQ}
            className={`bg-teal-500 text-black px-4 py-2 rounded hover:bg-teal-600 flex items-center gap-2 ${
              (loading || loadingFAQ) ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Generating...</span>
              </>
            ) : (
              <>
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span>Generate Manual</span>
              </>
            )}
          </button>
          {renderFAQButton()}
        </div>
      </div>
    </div>
  );

  const renderAddDataSourcePage = () => (
    <div className="p-4 w-full">
      <h2 className="text-xl font-semibold mb-4">Add Data Source</h2>
      <div className="grid grid-cols-1 gap-4 max-w-2xl">
        {/* PDF Upload Section */}
        <div>
          <label className="flex items-center">
            <input
              type="checkbox"
              className="mr-2"
              checked={dataSources.pdf.enabled}
              onChange={() => handleDataSourceToggle("pdf")}
            />
            <span>Upload PDF</span>
          </label>
          {dataSources.pdf.enabled && (
            <div className="mt-2">
              <label className="block">
                <span className="sr-only">Choose PDF</span>
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={handleFileUpload}
                  className="block w-full text-sm text-gray-500
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-md file:border-0
                    file:text-sm file:font-semibold
                    file:bg-teal-50 file:text-teal-700
                    hover:file:bg-teal-100"
                />
              </label>
              {dataSources.pdf.fileName && (
                <p className="mt-1 text-sm text-gray-600">
                  {dataSources.pdf.fileName}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Link Upload Section */}
        <div>
          <label className="flex items-center">
            <input
              type="checkbox"
              className="mr-2"
              checked={dataSources.link.enabled}
              onChange={() => handleDataSourceToggle("link")}
            />
            <span>Upload Link</span>
          </label>
          {dataSources.link.enabled && (
            <input
              type="text"
              className="mt-2 block w-full border border-gray-300 rounded-md p-2"
              placeholder="Enter link"
              value={dataSources.link.value}
              onChange={(e) =>
                handleDataSourceValueChange("link", e.target.value)
              }
            />
          )}
        </div>

        {/* Azure Blob Section */}
        <div>
          <label className="flex items-center">
            <input
              type="checkbox"
              className="mr-2"
              checked={dataSources.azureBlob.enabled}
              onChange={() => handleDataSourceToggle("azureBlob")}
            />
            <span>Azure Blob Storage</span>
          </label>
          {dataSources.azureBlob.enabled && (
            <input
              type="text"
              className="mt-2 block w-full border border-gray-300 rounded-md p-2"
              placeholder="Enter Azure Blob Storage details"
              value={dataSources.azureBlob.value}
              onChange={(e) =>
                handleDataSourceValueChange("azureBlob", e.target.value)
              }
            />
          )}
        </div>

        {/* Confluence Section */}
        <div>
          <label className="flex items-center">
            <input
              type="checkbox"
              className="mr-2"
              checked={dataSources.confluence.enabled}
              onChange={() => handleDataSourceToggle("confluence")}
            />
            <span>Confluence</span>
          </label>
          {dataSources.confluence.enabled && (
            <input
              type="text"
              className="mt-2 block w-full border border-gray-300 rounded-md p-2"
              placeholder="Enter Confluence details"
              value={dataSources.confluence.value}
              onChange={(e) =>
                handleDataSourceValueChange("confluence", e.target.value)
              }
            />
          )}
        </div>

        {error && <p className="text-red-500">{error}</p>}

        <button
          onClick={() => setActivePage("generateManual")}
          className="mt-4 bg-white text-black px-4 py-2 rounded hover:bg-gray-200 flex items-center gap-2"
        >
          {/* Inline Floppy Disk (Save) Icon */}
          <svg
            className="w-5 h-5 text-teal-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M5 3v18h14V7.5L15.5 3H5zM15 3v4h4"
            />
          </svg>
          Save Data Sources
        </button>
      </div>
    </div>
  );

  // Update the LoadingOverlay component
  const LoadingOverlay = () => {
    const isLoading = loading || loadingFAQ;
    
    if (!isLoading) return null;

    const currentMessages = loadingFAQ ? faqLoadingMessages : manualLoadingMessages;
    const currentStep = loadingFAQ ? currentFAQStep : currentLoadingStep;

    return (
      <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8 max-w-md w-11/12 text-center">
          <div className="relative inline-flex">
            <div className="w-16 h-16 relative">
              <div className="absolute inset-0 border-4 border-teal-100 rounded-full"></div>
              <div 
                className="absolute inset-0 border-4 border-teal-500 rounded-full animate-spin"
                style={{
                  borderRightColor: 'transparent',
                  borderBottomColor: 'transparent',
                  animationDuration: '550ms'
                }}
              ></div>
            </div>
          </div>
          <h3 className="mt-4 mb-2 text-lg font-medium text-gray-900">
            {currentMessages[currentStep] || "Processing..."}
          </h3>
          <p className="text-sm text-gray-500">
            Please wait while we process your request...
          </p>
          <div className="mt-4">
            <div className="space-y-2">
              {Object.entries(currentMessages).map(([step, message]) => (
                <div 
                  key={step} 
                  className={`flex items-center ${
                    currentStep === step ? 'text-teal-500' : 'text-gray-400'
                  }`}
                >
                  <div className={`w-2 h-2 rounded-full mr-2 ${
                    currentStep === step ? 'bg-teal-500' : 'bg-gray-300'
                  }`} />
                  <span className="text-sm">{message}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Update the FAQ button in your render function
  const renderFAQButton = () => (
    <button
      onClick={handleFAQ}
      disabled={loadingFAQ}
      className={`border border-gray-500 text-black px-4 py-2 rounded hover:bg-gray-100 flex items-center gap-2 ${
        loadingFAQ ? 'opacity-50 cursor-not-allowed' : ''
      }`}
    >
      {loadingFAQ ? (
        <>
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-teal-500"></div>
          <span>Generating...</span>
        </>
      ) : (
        <>
          <svg
            className="w-5 h-5 text-teal-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M8.228 9.228a4 4 0 115.544 0M12 16h.01"
            />
          </svg>
          <span>FAQ</span>
        </>
      )}
    </button>
  );

  // Update the PDF Preview Modal component
  const PDFPreviewModal = ({ pdfUrl, onClose, onDownload }) => {
    if (!pdfUrl) return null;
    
    const handleDownload = () => {
      // Create a link element
      const link = document.createElement('a');
      link.href = pdfUrl;
      link.download = `FAQ_${selectedItem}_${language}.pdf`; // Set the filename
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    };

    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-4 w-11/12 h-5/6 max-w-6xl flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">FAQ Preview</h2>
            <div className="flex gap-2">
              <button
                onClick={handleDownload}
                className="bg-teal-500 text-black px-4 py-2 rounded hover:bg-teal-600 flex items-center gap-2"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                  />
                </svg>
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
  };

  // Update the cleanup function
  const handleClosePreview = () => {
    if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
    }
    setShowPreview(false);
    setPdfUrl(null);
    setPdfBlob(null);
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden">
      <div className="flex flex-grow overflow-hidden">
        {/* Sidebar */}
        <div className="w-60 bg-gray-800 text-white h-full">
          <div className="p-4 border-b border-gray-700">
            <h2 className="text-lg font-semibold">Configuration</h2>
          </div>
          <ul>
            <li
              onClick={() => setActivePage("generateManual")}
              className={`p-4 cursor-pointer hover:bg-gray-700 flex items-center gap-2 ${
                activePage === "generateManual" ? "bg-gray-700" : ""
              }`}
            >
              {/* Inline Document Icon */}
              <svg
                className="w-5 h-5 text-teal-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M7 7h10M7 11h10M7 15h10M5 6a2 2 0 012-2h10a2 2 0 012 2v12a2 2 0 01-2 2H7a2 2 0 01-2-2V6z"
                />
              </svg>
              <span>Generate Manual</span>
            </li>
            <li
              onClick={() => setActivePage("addDataSource")}
              className={`p-4 cursor-pointer hover:bg-gray-700 flex items-center gap-2 ${
                activePage === "addDataSource" ? "bg-gray-700" : ""
              }`}
            >
              {/* Inline Plus Icon */}
              <svg
                className="w-5 h-5 text-teal-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 4v16m8-8H4"
                />
              </svg>
              <span>Add Data Source</span>
            </li>
          </ul>
        </div>

        {/* Main content */}
        <div className="flex-grow bg-white overflow-auto p-4">
          {activePage === "generateManual"
            ? renderGenerateManualPage()
            : renderAddDataSourcePage()}
        </div>
      </div>
      <LoadingOverlay />
      {showPreview && (
        <PDFPreviewModal
          pdfUrl={pdfUrl}
          onClose={handleClosePreview}
          onDownload={() => {
            // Implement download logic
          }}
        />
      )}
    </div>
  );
}
