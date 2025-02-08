"use client"
import { useState } from "react"
import { TextField, Select, MenuItem, Button, Grid, Box, Typography } from "@mui/material"

export default function UserManualGenerator() {
  const [link, setLink] = useState("")
  const [product, setProduct] = useState("")
  const [language, setLanguage] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const handleProductChange = (event) => {
    setProduct(event.target.value)
  }

  const handleLanguageChange = (event) => {
    setLanguage(event.target.value)
  }

  const handleLinkChange = (event) => {
    setLink(event.target.value)
  }

  const handleGenerateManual = async () => {
    if (!link || !language) {
      setError("Please provide both link and language")
      return
    }

    setLoading(true)
    setError("")

    try {
      const response = await fetch("http://localhost:8000/generate-manual", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          website_link: link,
          language: language
        }),
      })

      if (!response.ok) {
        throw new Error("Failed to generate manual")
      }

      // Handle PDF download
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `user_manual_${language}.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box sx={{ flexGrow: 1, p: 3, bgcolor: "background.paper" }}>
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
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Typography variant="subtitle1" gutterBottom>
            Link
          </Typography>
          <TextField 
            fullWidth 
            variant="outlined" 
            placeholder="Enter link here" 
            value={link}
            onChange={handleLinkChange}
            error={!!error && !link}
            helperText={error && !link ? "Link is required" : ""}
          />
        </Grid>
        <Grid item xs={12} md={6}>
          <Typography variant="subtitle1" gutterBottom>
            Language
          </Typography>
          <Select 
            fullWidth 
            value={language} 
            onChange={handleLanguageChange} 
            displayEmpty 
            variant="outlined"
            error={!!error && !language}
          >
            <MenuItem value="" disabled>
              Select a language
            </MenuItem>
            <MenuItem value="en">English</MenuItem>
            <MenuItem value="es">Spanish</MenuItem>
            <MenuItem value="fr">French</MenuItem>
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
          {loading ? "Generating..." : "Generate User Manual"}
        </Button>
      </Box>
    </Box>
  )
}