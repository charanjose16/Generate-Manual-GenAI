
import './App.css';

const DocumentationNav = () => {
  return (
    <div className="page-container">
        <div className="content-wrapper">
          <header className="header">
            <h1 className="app-title">Documentation Portal</h1>
            <p className="app-subtitle">Generate User Manual and FAQ</p>
          </header>

          <div className="form-container" style={{marginTop:"80px"}}>
            <div className="input-grid">
              <div className="form-group">
                <label htmlFor="link" className="form-label">
                  Link
                </label>
                <input
                  type="text"
                  id="link"
                  className="form-input"
                  placeholder="Enter link"
                />
              </div>
              
              <div className="form-group">
                <label htmlFor="products" className="form-label">
                  Products
                </label>
                <select
                  id="products"
                  className="form-select"
                >
                  <option value="">Select product</option>
                  <option value="product1">Product 1</option>
                  <option value="product2">Product 2</option>
                  <option value="product3">Product 3</option>
                </select>
              </div>
            </div>

            <div className="form-group language-group">
              <label htmlFor="language" className="form-label">
                Language
                <span className="required">*</span>
              </label>
              <select
                id="language"
                className="form-select lang"
                required
                style={{width:"48.5%"}}
              >
                <option value="">Select language</option>
                <option value="en">English</option>
                <option value="es">Spanish</option>
                <option value="fr">French</option>
              </select>
            </div>
          </div>

          <div className="button-container">
            <button className="button">User Manual</button>
            <button className="button">FAQ</button>
          </div>
        </div>
      </div>
  );
};

export default DocumentationNav;