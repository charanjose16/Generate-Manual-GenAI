import React from 'react';
import logo from '../assets/ustlogo.svg'; // Ensure the path is correct
import LinkedInIcon from '@mui/icons-material/LinkedIn';
import TwitterIcon from '@mui/icons-material/Twitter';
import FacebookIcon from '@mui/icons-material/Facebook';
import InstagramIcon from '@mui/icons-material/Instagram';
import YouTubeIcon from '@mui/icons-material/YouTube';

function Footer() {
    return (
        <div className="relative w-full h-24 flex flex-col bg-gradient-to-r from-[#09131D] to-[#16212D]">
            <div className="flex justify-between items-center px-4 h-full">
                {/* Logo Section */}
                <div className="flex items-center pl-8">
                    <img src={logo} alt="Company Logo" className="h-12" />
                </div>

                {/* Social Media Icons */}
                <div className="flex space-x-4 mr-8">
                    {/* LinkedIn Icon */}
                    <div className="text-white" style={{ fontSize: '36px' }}>
                        <LinkedInIcon />
                    </div>

                    {/* Twitter Icon */}
                    <div className="text-white" style={{ fontSize: '36px' }}>
                        <TwitterIcon />
                    </div>

                    {/* Facebook Icon */}
                    <div className="text-white" style={{ fontSize: '36px' }}>
                        <FacebookIcon />
                    </div>

                    {/* Instagram Icon */}
                    <div className="text-white" style={{ fontSize: '36px' }}>
                        <InstagramIcon />
                    </div>

                    {/* YouTube Icon */}
                    <div className="text-white" style={{ fontSize: '36px' }}>
                        <YouTubeIcon />
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Footer;
