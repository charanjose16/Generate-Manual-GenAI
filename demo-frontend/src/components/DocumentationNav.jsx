const DocumentationNav = () => {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex justify-center items-center">
        <div className="w-full max-w-4xl bg-white rounded-lg shadow-xl p-8 animate-fade-in">
          <header className="border-b border-gray-200 pb-6">
            <h1 className="text-3xl font-bold text-blue-600">Documentation Portal</h1>
            <p className="text-lg text-gray-600 mt-2">Generate User Manual and FAQ</p>
          </header>
  
          <div className="mt-10">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="flex flex-col space-y-2">
                <label htmlFor="link" className="text-sm font-medium text-gray-700">
                  Link
                </label>
                <input
                  type="text"
                  id="link"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter link"
                />
              </div>
  
              <div className="flex flex-col space-y-2">
                <label htmlFor="products" className="text-sm font-medium text-gray-700">
                  Products
                </label>
                <select
                  id="products"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 appearance-none bg-white 
                  bg-[url('data:image/svg+xml;charset=US-ASCII,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'24\' height=\'24\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%23666666\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'><polyline points=\'6 9 12 15 18 9\'></polyline></svg>')] 
                  bg-no-repeat bg-right-2 bg-center"
                >
                  <option value="">Select product</option>
                  <option value="product1">Product 1</option>
                  <option value="product2">Product 2</option>
                  <option value="product3">Product 3</option>
                </select>
              </div>
            </div>
  
            <div className="mt-6">
              <label htmlFor="language" className="text-sm font-medium text-gray-700">
                Language <span className="text-red-500">*</span>
              </label>
              <select
                id="language"
                className="w-full md:w-1/2 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 appearance-none bg-white 
                bg-[url('data:image/svg+xml;charset=US-ASCII,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'24\' height=\'24\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%23666666\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'><polyline points=\'6 9 12 15 18 9\'></polyline></svg>')] 
                bg-no-repeat bg-right-2 bg-center"
                required
              >
                <option value="">Select language</option>
                <option value="en">English</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
              </select>
            </div>
          </div>
  
          <div className="mt-12 flex justify-center space-x-8">
            <button className="px-6 py-2 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-semibold rounded-lg shadow-md hover:shadow-lg transform hover:-translate-y-1 transition-all duration-200">
              User Manual
            </button>
            <button className="px-6 py-2 bg-gradient-to-r from-blue-500 to-indigo-600 text-white font-semibold rounded-lg shadow-md hover:shadow-lg transform hover:-translate-y-1 transition-all duration-200">
              FAQ
            </button>
          </div>
        </div>
      </div>
    );
  };
  
  export default DocumentationNav;
  