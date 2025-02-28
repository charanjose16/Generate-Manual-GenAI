import React, { useState, useEffect, Fragment } from "react";
import { Listbox, Transition } from "@headlessui/react";
import {
  FaUpload,
  FaEdit,
  FaSave,
  FaArrowLeft,
  FaPlus,
  FaCog,
  FaTimes,
  FaFileAlt,
  FaChevronDown,
  FaCheck,
} from "react-icons/fa";

// Define your base URL from Vite's environment variable
const BASE_URL = import.meta.env.VITE_BASE_URL;

// Sidebar Component
const Sidebar = ({ activeView, setActiveView }) => {
  return (
    <div className="w-60 bg-gray-800 text-white h-full">
      <div className="p-4 border-b border-gray-700">
        <h2 className="text-lg font-semibold">Configuration</h2>
      </div>
      <ul>
        <li
          onClick={() => setActiveView("productConfiguration")}
          className={`p-4 cursor-pointer hover:bg-gray-700 flex items-center gap-2 transition-colors ${
            activeView === "productConfiguration" ? "bg-gray-700" : ""
          }`}
        >
          <FaCog className="w-5 h-5 text-teal-500" />
          <span>Product Configuration</span>
        </li>
        <li
          onClick={() => setActiveView("addTemplate")}
          className={`p-4 cursor-pointer hover:bg-gray-700 flex items-center gap-2 transition-colors ${
            activeView === "addTemplate" ? "bg-gray-700" : ""
          }`}
        >
          <FaPlus className="w-5 h-5 text-teal-500" />
          <span>Add Template</span>
        </li>
      </ul>
    </div>
  );
};

// Updated AddTemplate Component
const AddTemplate = ({ products, setActiveView }) => {
  const predefinedTemplate = `1. Customer & Market Needs
2. Product Performance & Specifications
3. Technological Innovations
4. Manufacturing & Feasibility
5. Compliance & Safety Standards`;

  const [templateMode, setTemplateMode] = useState("upload");
  const [customTemplate, setCustomTemplate] = useState("");
  const [fileName, setFileName] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);

  // States for customize mode
  const predefinedSections = [
    "Customer & Market Needs",
    "Product Performance & Specifications",
    "Technological Innovations",
    "Manufacturing & Feasibility",
    "Compliance & Safety Standards",
  ];
  const [selectedSections, setSelectedSections] = useState([]);
  const [extraCustom, setExtraCustom] = useState("");

  // Load template when product changes
  useEffect(() => {
    if (selectedProduct) {
      const productTemplates = JSON.parse(localStorage.getItem("productTemplates") || "{}");
      const template = productTemplates[selectedProduct.product_name] || "";
      setCustomTemplate(template);
    } else {
      setCustomTemplate("");
    }
  }, [selectedProduct]);

  const handleToggle = (mode) => {
    setTemplateMode(mode);
    setIsEditing(false);
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file || !selectedProduct) {
      if (!selectedProduct) alert("Please select a product first.");
      return;
    }
    const allowedTypes = [
      "text/plain",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/pdf",
    ];
    if (!allowedTypes.includes(file.type)) {
      alert("Only TXT, DOC, DOCX, or PDF files are allowed.");
      return;
    }
    setFileName(file.name);
    if (file.type === "application/pdf") {
      const formData = new FormData();
      formData.append("template_file", file);
      fetch(`${BASE_URL}/api/extract-pdf-text`, {
        method: "POST",
        body: formData,
      })
        .then((response) => response.json())
        .then((data) => {
          setCustomTemplate(data.extractedText);
          const productTemplates = JSON.parse(localStorage.getItem("productTemplates") || "{}");
          productTemplates[selectedProduct.product_name] = data.extractedText;
          localStorage.setItem("productTemplates", JSON.stringify(productTemplates));
          setIsEditing(false);
        })
        .catch((error) => {
          console.error("Error extracting PDF text:", error);
          alert("Failed to extract text from PDF.");
        });
    } else {
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target.result;
        setCustomTemplate(content);
        const productTemplates = JSON.parse(localStorage.getItem("productTemplates") || "{}");
        productTemplates[selectedProduct.product_name] = content;
        localStorage.setItem("productTemplates", JSON.stringify(productTemplates));
        setIsEditing(false);
      };
      reader.readAsText(file);
    }
  };

  const handleAddSection = (section) => {
    if (!selectedSections.includes(section)) {
      setSelectedSections([...selectedSections, section]);
    }
  };

  const handleRemoveSection = (section) => {
    setSelectedSections(selectedSections.filter((s) => s !== section));
  };

  const handleCustomizeSave = (e) => {
    e.preventDefault();
    if (!selectedProduct) {
      alert("Please select a product first.");
      return;
    }
    const combinedTemplate = [
      ...selectedSections,
      extraCustom.trim() ? extraCustom.trim() : null,
    ]
      .filter(Boolean)
      .join("\n");
    setCustomTemplate(combinedTemplate);
    const productTemplates = JSON.parse(localStorage.getItem("productTemplates") || "{}");
    productTemplates[selectedProduct.product_name] = combinedTemplate;
    localStorage.setItem("productTemplates", JSON.stringify(productTemplates));
    setIsEditing(false);
  };

  const handleEditClick = () => {
    setIsEditing(true);
  };

  const handleSave = (e) => {
    e.preventDefault();
    if (!selectedProduct) {
      alert("Please select a product first.");
      return;
    }
    const productTemplates = JSON.parse(localStorage.getItem("productTemplates") || "{}");
    productTemplates[selectedProduct.product_name] = customTemplate;
    localStorage.setItem("productTemplates", JSON.stringify(productTemplates));
    setIsEditing(false);
  };

  const handleBackToForm = () => {
    setActiveView("productConfiguration");
  };

  return (
    <div className="min-h-screen w-full bg-gray-100 overflow-auto">
      <div className="w-full px-4 py-6 sm:px-6 lg:px-8">
        <div className="mb-6 flex items-center justify-between">
          <button
            onClick={handleBackToForm}
            className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
          >
            <FaArrowLeft className="mr-1 text-teal-500" /> Back
          </button>
        </div>
        <div className="bg-white shadow rounded-lg overflow-hidden min-h-[70vh]">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-medium text-gray-800">
              Configure Template Content
            </h2>
          </div>
          <div className="px-6 py-5 min-h-[calc(100vh-200px)] overflow-auto">
            {/* Product Selection Dropdown */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Product
              </label>
              <Listbox value={selectedProduct} onChange={setSelectedProduct}>
                {({ open }) => (
                  <div className="relative w-full">
                    <Listbox.Button className="w-full bg-gray-200 text-black p-2 rounded-md border border-gray-300 focus:ring-2 focus:ring-teal-500 text-left">
                      <span>
                        {selectedProduct ? selectedProduct.product_name : "Select Product"}
                      </span>
                      <FaChevronDown
                        className={`absolute right-3 top-2.5 text-black transition-transform duration-200 ${
                          open ? "rotate-180" : ""
                        }`}
                      />
                    </Listbox.Button>
                    <Transition
                      as={Fragment}
                      leave="transition ease-in duration-100"
                      leaveFrom="opacity-100"
                      leaveTo="opacity-0"
                    >
                      <Listbox.Options className="absolute z-10 mt-1 w-full bg-gray-200 shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-gray-300 overflow-auto focus:outline-none">
                        {products.length > 0 ? (
                          products.map((prod, index) => (
                            <Listbox.Option
                              key={index}
                              value={prod}
                              className={({ active }) =>
                                `cursor-pointer select-none relative py-2 pl-10 pr-4 ${
                                  active ? "bg-teal-300 text-black" : "text-black"
                                }`
                              }
                            >
                              {({ selected }) => (
                                <>
                                  <span
                                    className={`block truncate ${
                                      selected ? "font-medium" : "font-normal"
                                    }`}
                                  >
                                    {prod.product_name}
                                  </span>
                                  {selected && (
                                    <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-black">
                                      <FaCheck className="w-5 h-5" />
                                    </span>
                                  )}
                                </>
                              )}
                            </Listbox.Option>
                          ))
                        ) : (
                          <div className="py-2 px-3 text-gray-500">Loading products...</div>
                        )}
                      </Listbox.Options>
                    </Transition>
                  </div>
                )}
              </Listbox>
            </div>

            {/* Template Configuration (Only if Product is Selected) */}
            {selectedProduct ? (
              <>
                <div className="flex space-x-4 mb-6">
                  <button
                    onClick={() => handleToggle("upload")}
                    className={`px-4 py-2 rounded ${
                      templateMode === "upload"
                        ? "bg-teal-300 text-black"
                        : "bg-gray-200 text-gray-700"
                    }`}
                  >
                    Upload Template
                  </button>
                  <button
                    onClick={() => handleToggle("customize")}
                    className={`px-4 py-2 rounded ${
                      templateMode === "customize"
                        ? "bg-teal-300 text-black"
                        : "bg-gray-200 text-gray-700"
                    }`}
                  >
                    Customize Template
                  </button>
                </div>

                {templateMode === "upload" ? (
                  <div className="mb-4">
                    {!isEditing && (
                      <div className="bg-gray-50 p-4 border rounded">
                        <div className="mb-3">
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Upload Template File
                          </label>
                          <div className="mt-1 flex items-center">
                            <label className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 cursor-pointer transition-colors">
                              <FaUpload className="mr-2 text-teal-500" /> Browse Files
                              <input
                                type="file"
                                accept=".txt, .doc, .docx, .pdf"
                                onChange={handleFileUpload}
                                className="sr-only"
                              />
                            </label>
                            <span className="ml-3 text-sm text-gray-500">
                              {fileName || "No file selected"}
                            </span>
                          </div>
                          <p className="mt-2 text-xs text-gray-500">
                            Accepted formats: TXT, DOC, DOCX, PDF
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="mb-6">
                      <h3 className="text-md font-medium text-gray-700 mb-3">
                        Predefined Template Sections
                      </h3>
                      <div className="space-y-2">
                        {predefinedSections.map((section, index) => (
                          <div
                            key={index}
                            className="flex items-center justify-between border p-2 rounded bg-gray-50"
                          >
                            <span>{section}</span>
                            <button
                              onClick={() => handleAddSection(section)}
                              className="px-2 py-1 bg-teal-300 text-black rounded hover:bg-teal-400"
                            >
                              <FaPlus />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h3 className="text-md font-medium text-gray-700 mb-3">
                        Selected Sections
                      </h3>
                      {selectedSections.length > 0 ? (
                        <ul className="list-disc pl-5 mb-4">
                          {selectedSections.map((section, index) => (
                            <li key={index} className="flex items-center">
                              {section}
                              <button
                                onClick={() => handleRemoveSection(section)}
                                className="ml-2 text-red-500"
                              >
                                <FaTimes />
                              </button>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-gray-500 mb-4">
                          No sections selected yet.
                        </p>
                      )}
                    </div>
                    <div className="mb-6">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Additional Custom Content
                      </label>
                      <textarea
                        className="w-full p-3 border rounded-md shadow-sm focus:ring-2 focus:ring-teal-300 focus:border-teal-300 resize-none transition-colors"
                        rows="4"
                        value={extraCustom}
                        onChange={(e) => setExtraCustom(e.target.value)}
                        placeholder="Enter any additional custom content here..."
                      ></textarea>
                    </div>
                    <div className="flex justify-end">
                      <button
                        onClick={handleCustomizeSave}
                        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-black bg-teal-300 hover:bg-teal-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-teal-500 transition-colors"
                      >
                        <FaSave className="mr-2 text-teal-500" /> Save Template
                      </button>
                    </div>
                  </div>
                )}

                {customTemplate && !isEditing && (
                  <div className="mt-6">
                    <h3 className="text-md font-medium text-gray-700 mb-3">
                      Current Template for {selectedProduct.product_name}
                    </h3>
                    <div className="p-4 border rounded bg-gray-50 text-gray-800 whitespace-pre-wrap mb-3">
                      {customTemplate}
                    </div>
                    <button
                      type="button"
                      onClick={handleEditClick}
                      className="inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-black bg-teal-300 hover:bg-teal-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-teal-500 transition-colors"
                    >
                      <FaEdit className="mr-2 text-teal-500" /> Edit Template
                    </button>
                  </div>
                )}

                {isEditing && (
                  <div className="space-y-4">
                    <form onSubmit={handleSave}>
                      <div className="mb-3">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Edit Template Content for {selectedProduct.product_name}
                        </label>
                        <textarea
                          className="w-full p-3 border rounded-md shadow-sm focus:ring-2 focus:ring-teal-300 focus:border-teal-300 resize-none transition-colors"
                          rows="8"
                          value={customTemplate}
                          onChange={(e) => setCustomTemplate(e.target.value)}
                          placeholder="Enter template content here..."
                        ></textarea>
                      </div>
                      <div className="flex justify-end">
                        <button
                          type="button"
                          onClick={() => setIsEditing(false)}
                          className="mr-3 inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-teal-500 transition-colors"
                        >
                          <FaTimes className="mr-2 text-teal-500" /> Cancel
                        </button>
                        <button
                          type="submit"
                          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-black bg-teal-300 hover:bg-teal-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-teal-500 transition-colors"
                        >
                          <FaSave className="mr-2 text-teal-500" /> Save Template
                        </button>
                      </div>
                    </form>
                  </div>
                )}
              </>
            ) : (
              <p className="text-gray-500">
                Please select a product to configure the template.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Updated Form Component
const Form = ({ setLoading, setProgress, products, loading, progress }) => {
  const [product, setProduct] = useState(() => {
    const savedProduct = localStorage.getItem("product");
    try {
      return savedProduct ? JSON.parse(savedProduct) : "";
    } catch (e) {
      return savedProduct || "";
    }
  });
  const [details, setDetails] = useState(localStorage.getItem("details") || "");
  const [persona, setPersona] = useState("product_manager");

  const personaOptions = [
    { id: 1, value: "product_manager", label: "Product Manager" },
    { id: 2, value: "product_engineer", label: "Product Engineer" },
  ];

  useEffect(() => {
    localStorage.setItem(
      "product",
      typeof product === "object" && product !== null
        ? JSON.stringify(product)
        : product
    );
    localStorage.setItem("details", details);
  }, [product, details]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setProgress("Initializing PDF generation...");

    const formData = new FormData();
    formData.append(
      "product_category",
      typeof product === "object" && product !== null
        ? product.product_name
        : product
    );
    formData.append("product_details", details);
    const productTemplates = JSON.parse(localStorage.getItem("productTemplates") || "{}");
    const templateForProduct = productTemplates[product.product_name] || "";
    formData.append("custom_template", templateForProduct);
    formData.append("persona", persona);

    try {
      const response = await fetch(
        `${BASE_URL}/api/generate-product-designer-pdf`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok)
        throw new Error("Failed to initiate PDF generation");

      const { job_id } = await response.json();
      setProgress("Job started...");

      const wsUrl = BASE_URL.replace("http", "ws");
      const ws = new WebSocket(`${wsUrl}/api/ws/progress/${job_id}`);
      ws.onmessage = (event) => {
        setProgress(event.data);
        if (event.data.startsWith("PDF is ready")) {
          ws.close();
          setLoading(false);
          localStorage.removeItem("product");
          localStorage.removeItem("details");
          setProduct("");
          setDetails("");
          window.location.href = `${BASE_URL}/api/download/${job_id}`;
        }
      };
      ws.onerror = () => {
        setLoading(false);
        alert("WebSocket error occurred");
      };
    } catch (error) {
      console.error("Error:", error);
      setLoading(false);
      alert("An error occurred while generating the PDF.");
    }
  };

  return (
    <div className="relative w-full h-full min-h-screen">
      <div
        className={
          loading
            ? "filter blur-sm opacity-30 transition-all duration-300 h-full"
            : "h-full"
        }
      >
        <div className="bg-white p-6 rounded-md shadow-md h-full">
          <form onSubmit={handleSubmit} className="h-full flex flex-col">
            <label className="block mb-2 font-medium">Product</label>
            <div className="relative mb-4">
              <Listbox value={product} onChange={setProduct}>
                {({ open }) => (
                  <div className="relative w-full">
                    <Listbox.Button className="w-full bg-gray-200 text-black p-2 rounded-md border border-gray-300 focus:ring-2 focus:ring-teal-500 text-left">
                      <span>
                        {typeof product === "object" && product !== null
                          ? product.product_name
                          : product || "Select Product"}
                      </span>
                      <FaChevronDown
                        className={`absolute right-3 top-2.5 text-black transition-transform duration-200 ${
                          open ? "rotate-180" : ""
                        }`}
                      />
                    </Listbox.Button>
                    <Transition
                      as={Fragment}
                      leave="transition ease-in duration-100"
                      leaveFrom="opacity-100"
                      leaveTo="opacity-0"
                    >
                      <Listbox.Options className="absolute z-10 mt-1 w-full bg-gray-200 shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-gray-300 overflow-auto focus:outline-none">
                        {products.length > 0 ? (
                          products.map((prod, index) => (
                            <Listbox.Option
                              key={index}
                              value={prod}
                              className={({ active }) =>
                                `cursor-pointer select-none relative py-2 pl-10 pr-4 ${
                                  active
                                    ? "bg-teal-300 text-black"
                                    : "text-black"
                                }`
                              }
                            >
                              {({ selected }) => (
                                <>
                                  <span
                                    className={`block truncate ${
                                      selected ? "font-medium" : "font-normal"
                                    }`}
                                  >
                                    {prod.product_name}
                                  </span>
                                  {selected && (
                                    <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-black">
                                      <FaCheck className="w-5 h-5" />
                                    </span>
                                  )}
                                </>
                              )}
                            </Listbox.Option>
                          ))
                        ) : (
                          <div className="py-2 px-3 text-gray-500">
                            Loading products...
                          </div>
                        )}
                      </Listbox.Options>
                    </Transition>
                  </div>
                )}
              </Listbox>
            </div>

            <label className="block mb-2 font-medium">Persona</label>
            <div className="relative mb-4">
              <Listbox value={persona} onChange={setPersona}>
                {({ open }) => (
                  <div className="relative w-full">
                    <Listbox.Button className="w-full bg-gray-200 text-black p-2 rounded-md border border-gray-300 focus:ring-2 focus:ring-teal-500 text-left">
                      <span>
                        {personaOptions.find(
                          (option) => option.value === persona
                        ).label}
                      </span>
                      <FaChevronDown
                        className={`absolute right-3 top-2.5 text-black transition-transform duration-200 ${
                          open ? "rotate-180" : ""
                        }`}
                      />
                    </Listbox.Button>
                    <Transition
                      as={Fragment}
                      leave="transition ease-in duration-100"
                      leaveFrom="opacity-100"
                      leaveTo="opacity-0"
                    >
                      <Listbox.Options className="absolute z-10 mt-1 w-full bg-gray-200 shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-gray-300 overflow-auto focus:outline-none">
                        {personaOptions.map((option) => (
                          <Listbox.Option
                            key={option.id}
                            value={option.value}
                            className={({ active }) =>
                              `cursor-pointer select-none relative py-2 pl-10 pr-4 ${
                                active ? "bg-teal-300 text-black" : "text-black"
                              }`
                            }
                          >
                            {({ selected }) => (
                              <>
                                <span
                                  className={`block truncate ${
                                    selected ? "font-medium" : "font-normal"
                                  }`}
                                >
                                  {option.label}
                                </span>
                                {selected && (
                                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-black">
                                    <FaCheck className="w-5 h-5" />
                                  </span>
                                )}
                              </>
                            )}
                          </Listbox.Option>
                        ))}
                      </Listbox.Options>
                    </Transition>
                  </div>
                )}
              </Listbox>
            </div>

            <label className="block mb-2 font-medium">Product Details</label>
            <textarea
              className="w-full p-2 border rounded mb-4 focus:ring-2 focus:ring-teal-500 transition-colors"
              value={details}
              onChange={(e) => setDetails(e.target.value)}
              placeholder="Enter product details"
              rows={4}
              disabled={loading}
            />

            <button
              type="submit"
              className="bg-teal-300 text-black w-full py-2 rounded hover:bg-teal-400 disabled:bg-teal-300 mt-4 transition-colors flex items-center justify-center uppercase"
              disabled={loading}
            >
              <FaFileAlt className="mr-2 text-teal-500" />
              Design Specification
            </button>
          </form>
        </div>
      </div>
      {loading && (
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50 bg-white p-8 rounded-lg shadow-xl">
          <div className="flex flex-col items-center">
            <div className="w-20 h-20 border-8 border-gray-200 border-t-teal-300 rounded-full animate-spin"></div>
            <p className="mt-6 text-xl font-medium text-gray-800">{progress}</p>
          </div>
        </div>
      )}
    </div>
  );
};

// Main ProductConfigurator Component
const ProductConfigurator = () => {
  const [activeView, setActiveView] = useState("productConfiguration");
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");

  useEffect(() => {
    const fetchProducts = async () => {
      try {
        const response = await fetch(`${BASE_URL}/api/products`);
        if (!response.ok) throw new Error("Failed to fetch products");
        const data = await response.json();
        setProducts(data.products);
      } catch (error) {
        console.error("Error fetching products:", error);
      }
    };
    fetchProducts();
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden">
      <div className="flex flex-grow overflow-hidden">
        <Sidebar activeView={activeView} setActiveView={setActiveView} />
        <div className="flex-grow bg-white overflow-auto p-4">
          {activeView === "productConfiguration" && (
            <Form
              setLoading={setLoading}
              setProgress={setProgress}
              products={products}
              loading={loading}
              progress={progress}
            />
          )}
          {activeView === "addTemplate" && (
            <AddTemplate
              products={products}
              setActiveView={setActiveView}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default ProductConfigurator;