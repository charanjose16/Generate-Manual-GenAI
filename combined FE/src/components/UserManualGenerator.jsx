import { useState, useEffect } from "react";
import { Listbox, Transition } from "@headlessui/react";
import axios from "axios";
import PropTypes from 'prop-types';

// Inline SVG icons for country flags
const countryIcons = {
  en: (
    <svg
      className="w-5 h-5 inline-block mr-1"
      viewBox="0 0 60 40"
      xmlns="http://www.w3.org/2000/svg"
    >
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

// PDF Preview Modal (for FAQ)
function PDFPreviewModal({ pdfUrl, onClose, selectedItem, language }) {
  if (!pdfUrl) return null;

  const handleDownload = () => {
    const link = document.createElement("a");
    link.href = pdfUrl;
    link.download = `FAQ_${selectedItem}_${language}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-4 w-11/12 max-w-6xl h-5/6 flex flex-col">
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

PDFPreviewModal.propTypes = {
  pdfUrl: (props, propName, componentName) => {
    if (props[propName] && typeof props[propName] !== "string") {
      return new Error(`${propName} in ${componentName} must be a string`);
    }
  },
  onClose: () => {},
  selectedItem: () => {},
  language: () => {},
};

// Loading Overlay Component
function LoadingOverlay({ isLoading, progressMessage, progressPercentage }) {
  if (!isLoading) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        backgroundColor: "rgba(0, 0, 0, 0.6)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          backgroundColor: "white",
          padding: "24px",
          borderRadius: "8px",
          boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
          textAlign: "center",
          maxWidth: "400px",
        }}
      >
        <div
          style={{
            display: "inline-block",
            width: "40px",
            height: "40px",
            border: "4px solid rgba(0, 0, 0, 0.1)",
            borderRadius: "50%",
            borderTopColor: "#14b8a6",
            animation: "spin 1s ease-in-out infinite",
            marginBottom: "16px",
          }}
        />
        <p style={{ fontSize: "16px", color: "#1f2937", margin: "0 0 16px 0" }}>
          {progressMessage}
        </p>
        <div style={{ 
          width: "100%", 
          backgroundColor: "#e5e7eb", 
          borderRadius: "4px", 
          overflow: "hidden" 
        }}>
          <div style={{ 
            height: "8px", 
            width: `${progressPercentage}%`, 
            backgroundColor: "#14b8a6",
            transition: "width 0.3s ease-in-out"
          }} />
        </div>
        <p style={{ fontSize: "14px", color: "#6b7280", marginTop: "8px" }}>
          {progressPercentage}% Complete
        </p>
      </div>
      <style>
        {`
          @keyframes spin {
            to {
              transform: rotate(360deg);
            }
          }
        `}
      </style>
    </div>
  );
}

LoadingOverlay.propTypes = {
  isLoading: PropTypes.bool.isRequired,
  progressMessage: PropTypes.string.isRequired,
  progressPercentage: PropTypes.number.isRequired,
};

export default function UserManualGenerator() {
  const [language, setLanguage] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [progressMessage, setProgressMessage] = useState("");
  const [progressPercentage, setProgressPercentage] = useState(0);
  const [error, setError] = useState("");
  const [products, setProducts] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState("");
  const [selectedSubProduct, setSelectedSubProduct] = useState("");
  const [selectedItem, setSelectedItem] = useState("");
  const [activePage, setActivePage] = useState("generateManual");
  const [fileFormat, setFileFormat] = useState("");
  const [uploadedFile, setUploadedFile] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [clientId, setClientId] = useState("");

  const baseUrl = import.meta.env.VITE_BASE_URL;
  axios.defaults.headers.common["Access-Control-Allow-Origin"] = "*";

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get(`${baseUrl}/products`);
        setProducts(response.data.products);
      } catch (err) {
        setError(`Failed to load products: ${err.message}`);
      }
    };
    fetchData();
  }, [baseUrl]);

  useEffect(() => {
    const newClientId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setClientId(newClientId);
  }, []);

  useEffect(() => {
    if (isGenerating) {
      const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
      const sseUrl = `${protocol}//${baseUrl.replace(/^https?:\/\//, '')}/sseusecase2/progress/${clientId}`;
      console.log(`Connecting to SSE: ${sseUrl}`);
      const eventSource = new EventSource(sseUrl);
  
      // Listen for "progress" events
      eventSource.addEventListener("progress", (event) => {
        console.log("Received progress event:", event.data);
        const data = JSON.parse(event.data);
        setProgressMessage(data.message);
        setProgressPercentage(data.percentage);
      });
  
      // Listen for "complete" events
      eventSource.addEventListener("complete", (event) => {
        console.log("Received complete event:", event.data);
        const data = JSON.parse(event.data);
        setProgressMessage(data.message);
        setProgressPercentage(data.percentage);
        eventSource.close();
        setIsGenerating(false);
      });
  
      // Handle connection errors
      eventSource.onerror = (error) => {
        console.error("SSE connection error:", error);
        setProgressMessage("Connection issue with progress updates...");
        eventSource.close();
        setIsGenerating(false);
      };
  
      // Cleanup on unmount
      return () => {
        eventSource.close();
      };
    }
  }, [isGenerating, clientId, baseUrl]);

  const handleProductChange = (value) => {
    if (!isGenerating) {
      setSelectedProduct(value);
      setSelectedSubProduct("");
      setSelectedItem("");
      if (error) setError("");
    }
  };

  const handleSubProductChange = (value) => {
    if (!isGenerating) {
      setSelectedSubProduct(value);
      setSelectedItem("");
      if (error) setError("");
    }
  };

  const handleFileUpload = (event) => {
    if (!isGenerating) {
      const file = event.target.files[0];
      if (file) {
        const allowedTypes = {
          pdf: "application/pdf",
          document: ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"], // Both .docx and .doc
          text: "text/plain",
        };
  
        if (fileFormat === "document") {
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
        setError(`Please upload a valid ${fileFormat.toUpperCase()} file. For documents, both .doc and .docx are supported.`);
        setUploadedFile(null);
      }
    }
  };

  const handleGenerateManual = async () => {
    if (!language || !selectedItem) {
      setError("Please fill in all required fields.");
      return;
    }
    setIsGenerating(true);
    setError("");
    setProgressPercentage(0);
    setProgressMessage("Starting...");

    try {
      const formData = new FormData();
      formData.append("product_category", selectedItem);
      formData.append("language", language);
      formData.append("client_id", clientId);
      if (uploadedFile) {
        formData.append("rag_source", uploadedFile);
      }

      const response = await axios.post(`${baseUrl}/generate-manual`, formData, {
        responseType: "blob",
      });

      const url = window.URL.createObjectURL(
        new Blob([response.data], { type: "application/pdf" })
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = `user_manual_${selectedItem}_${language}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      setSelectedProduct("");
      setSelectedSubProduct("");
      setSelectedItem("");
      setLanguage("");
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
      setIsGenerating(false);
    } finally {
      setUploadedFile(null);
      setFileFormat("");
    }
  };

  const handleFAQ = async () => {
    if (!language || !selectedItem) {
      setError("Please fill in all required fields.");
      return;
    }
    setIsGenerating(true);
    setError("");
    setProgressPercentage(0);
    setProgressMessage("Starting...");

    try {
      const formData = new FormData();
      formData.append("product_category", selectedItem);
      formData.append("language", language);
      formData.append("client_id", clientId);

      const response = await axios.post(`${baseUrl}/generate-faq`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      if (response.data && response.data.pdf_base64) {
        const byteCharacters = atob(response.data.pdf_base64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: "application/pdf" });
        const url = URL.createObjectURL(blob);
        setPdfUrl(url);
        setShowPreview(true);
        setSelectedProduct("");
        setSelectedSubProduct("");
        setSelectedItem("");
        setLanguage("");
      } else {
        throw new Error("Invalid PDF data received");
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to generate FAQ");
      setIsGenerating(false);
    } finally {
      setUploadedFile(null);
      setFileFormat("");
    }
  };

  const handleClosePreview = () => {
    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl);
    }
    setShowPreview(false);
    setPdfUrl(null);
  };

  const renderGenerateManualPage = () => (
    <div className="p-4 w-full">
      <h2 className="text-xl font-semibold mb-4">Generate User Manual</h2>
      <div className="grid grid-cols-1 gap-4 max-w-2xl relative">
        <div className="relative">
          <label className="block mb-1">Product</label>
          <Listbox value={selectedProduct} onChange={handleProductChange}>
            {({ open }) => (
              <div className="relative">
                <Listbox.Button className="relative w-full py-2 pl-3 pr-10 text-left bg-white border border-gray-300 rounded-md shadow-sm cursor-default focus:outline-none">
                  <span className="block truncate">
                    {selectedProduct || "Select a product"}
                  </span>
                </Listbox.Button>

                <Transition
                  show={open}
                  enter="transition duration-100 ease-out"
                  enterFrom="transform scale-95 opacity-0"
                  enterTo="transform scale-100 opacity-100"
                  leave="transition duration-75 ease-out"
                  leaveFrom="transform scale-100 opacity-100"
                  leaveTo="transform scale-95 opacity-0"
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
              </div>
            )}
          </Listbox>
        </div>

        {selectedProduct && (
          <div className="relative">
            <label className="block mb-1">Sub-Product</label>
            <Listbox value={selectedSubProduct} onChange={handleSubProductChange}>
              {({ open }) => (
                <div className="relative">
                  <Listbox.Button className="relative w-full py-2 pl-3 pr-10 text-left bg-white border border-gray-300 rounded-md shadow-sm cursor-default focus:outline-none">
                    <span className="block truncate">
                      {selectedSubProduct || "Select a sub-product"}
                    </span>
                  </Listbox.Button>

                  <Transition
                    show={open}
                    enter="transition duration-100 ease-out"
                    enterFrom="transform scale-95 opacity-0"
                    enterTo="transform scale-100 opacity-100"
                    leave="transition duration-75 ease-out"
                    leaveFrom="transform scale-100 opacity-100"
                    leaveTo="transform scale-95 opacity-0"
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
                </div>
              )}
            </Listbox>
          </div>
        )}

        {selectedSubProduct && (
          <div className="relative">
            <label className="block mb-1">Items</label>
            <Listbox value={selectedItem} onChange={setSelectedItem}>
              {({ open }) => (
                <div className="relative">
                  <Listbox.Button className="relative w-full py-2 pl-3 pr-10 text-left bg-white border border-gray-300 rounded-md shadow-sm cursor-default focus:outline-none">
                    <span className="block truncate">
                      {selectedItem || "Select an item"}
                    </span>
                  </Listbox.Button>

                  <Transition
                    show={open}
                    enter="transition duration-100 ease-out"
                    enterFrom="transform scale-95 opacity-0"
                    enterTo="transform scale-100 opacity-100"
                    leave="transition duration-75 ease-out"
                    leaveFrom="transform scale-100 opacity-100"
                    leaveTo="transform scale-95 opacity-0"
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
                </div>
              )}
            </Listbox>
          </div>
        )}

        <div className="relative">
          <label className="block mb-1">Language</label>
          <Listbox value={language} onChange={setLanguage}>
            {({ open }) => (
              <div className="relative">
                <Listbox.Button className="relative w-full py-2 pl-3 pr-10 text-left bg-white border border-gray-300 rounded-md shadow-sm cursor-default focus:outline-none">
                  <span className="block truncate">
                    {language
                      ? (() => {
                          const selected = languages.find(
                            (l) => l.code === language
                          );
                          return (
                            <>
                              {countryIcons[language]} {selected.name}
                            </>
                          );
                        })()
                      : "Select a language"}
                  </span>
                </Listbox.Button>

                <Transition
                  show={open}
                  enter="transition duration-100 ease-out"
                  enterFrom="transform scale-95 opacity-0"
                  enterTo="transform scale-100 opacity-100"
                  leave="transition duration-75 ease-out"
                  leaveFrom="transform scale-100 opacity-100"
                  leaveTo="transform scale-95 opacity-0"
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
                            {countryIcons[lang.code]} {lang.name}
                          </span>
                        )}
                      </Listbox.Option>
                    ))}
                  </Listbox.Options>
                </Transition>
              </div>
            )}
          </Listbox>
        </div>

        {error && <p className="text-red-500">{error}</p>}

        <div className="flex justify-center gap-4 mt-4">
          <button
            onClick={handleGenerateManual}
            disabled={isGenerating}
            style={{
              backgroundColor: "white",
              color: "black",
              padding: "8px 16px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              cursor: isGenerating ? "not-allowed" : "pointer",
              opacity: isGenerating ? 0.5 : 1,
              border: "none",
            }}
          >
            <svg
              className="w-5 h-5 text-teal-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M7 7h10M7 11h10M7 15h10M5 6a2 2 0 012-2h10a2 2 0 012 2v12a2 2 0 01-2 2H7a2 2 0 01-2-2V6z"
              />
            </svg>
            GENERATE USER MANUAL
          </button>
          <button
            onClick={handleFAQ}
            disabled={isGenerating}
            style={{
              border: "1px solid #6b7280",
              color: "black",
              padding: "8px 16px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              cursor: isGenerating ? "not-allowed" : "pointer",
              opacity: isGenerating ? 0.5 : 1,
              backgroundColor: "white",
            }}
          >
            <svg
              className="w-5 h-5 text-teal-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M8.228 9.228a4 4 0 115.544 0M12 16h.01"
              />
            </svg>
            FAQ
          </button>
        </div>
      </div>
    </div>
  );

  const renderAddDataSourcePage = () => (
    <div className="p-4 w-full">
      <h2 className="text-xl font-semibold mb-4">Add Data Source</h2>
      <div className="grid grid-cols-1 gap-4 max-w-2xl">
        <div>
          <label className="block mb-1">Select File Format</label>
          <select
            value={fileFormat}
            onChange={(e) => {
              if (!isGenerating) {
                setFileFormat(e.target.value);
                setUploadedFile(null);
              }
            }}
            className="block w-1/2 border border-gray-300 rounded-md p-2"
            disabled={isGenerating}
          >
            <option value="" disabled>
              Select format
            </option>
            <option value="pdf">PDF</option>
            <option value="document">Document (.docx, .doc)</option>
            <option value="text">Text</option>
          </select>
        </div>

        {fileFormat && (
          <div>
            <button
              type="button"
              className="mt-2 inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-base text-black bg-white hover:bg-gray-200"
              onClick={() => !isGenerating && document.getElementById('fileInput').click()}
              disabled={isGenerating}
            >
              {uploadedFile ? uploadedFile.name : "Choose File"}
            </button>
            <input
              id="fileInput"
              type="file"
              key={fileFormat}
              hidden
              onChange={handleFileUpload}
              accept={
                fileFormat === "pdf"
                  ? "application/pdf"
                  : fileFormat === "document"
                  ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword" // Both .docx and .doc
                  : "text/plain"
              }
              disabled={isGenerating}
            />
          </div>
        )}

        {error && <p className="text-red-500">{error}</p>}

        <button
          onClick={() => !isGenerating && setActivePage("generateManual")}
          className="mt-4 bg-white text-black px-4 py-2 rounded hover:bg-gray-200 flex items-center gap-2"
          disabled={isGenerating}
        >
          <svg
            className="w-5 h-5 text-teal-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M5 3v18h14V7.5L15.5 3H5zM15 3v4h4"
            />
          </svg>
          Save File
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden">
      <div className="flex flex-grow overflow-hidden">
        <div className="w-60 bg-gray-800 text-white h-full">
          <div className="p-4 border-b border-gray-700">
            <h2 className="text-lg font-semibold">Configuration</h2>
          </div>
          <ul>
            <li
              onClick={() => !isGenerating && setActivePage("generateManual")}
              className={`p-4 cursor-pointer hover:bg-gray-700 flex items-center gap-2 ${
                activePage === "generateManual" ? "bg-gray-700" : ""
              } ${isGenerating ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <svg
                className="w-5 h-5 text-teal-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
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
              onClick={() => !isGenerating && setActivePage("addDataSource")}
              className={`p-4 cursor-pointer hover:bg-gray-700 flex items-center gap-2 ${
                activePage === "addDataSource" ? "bg-gray-700" : ""
              } ${isGenerating ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <svg
                className="w-5 h-5 text-teal-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
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

        <div className="flex-grow bg-white overflow-auto p-4">
          {activePage === "generateManual"
            ? renderGenerateManualPage()
            : renderAddDataSourcePage()}
        </div>
      </div>
      {showPreview && (
        <PDFPreviewModal
          pdfUrl={pdfUrl}
          onClose={handleClosePreview}
          selectedItem={selectedItem}
          language={language}
        />
      )}
      <LoadingOverlay 
        isLoading={isGenerating} 
        progressMessage={progressMessage} 
        progressPercentage={progressPercentage} 
      />
    </div>
  );
}