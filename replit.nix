{ pkgs }: {
  deps = [
     pkgs.pkg-config
     pkgs.libffi
     pkgs.rustc
     pkgs.libiconv
     pkgs.cargo
     pkgs.zlib
     pkgs.tk
     pkgs.tcl
     pkgs.openjpeg
     pkgs.libxcrypt
     pkgs.libwebp
     pkgs.libtiff
     pkgs.libjpeg
     pkgs.libimagequant
     pkgs.lcms2
     pkgs.freetype
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.flask
    pkgs.python311Packages.requests
    pkgs.python311Packages.beautifulsoup4
    pkgs.python311Packages.pillow
    pkgs.python311Packages.pymongo
    pkgs.python311Packages.bcrypt
    pkgs.openssl
    pkgs.cacert
    pkgs.gcc
  ];
  env = {
    PYTHONBIN = "${pkgs.python311}/bin/python3.11";
    LANG = "en_US.UTF-8";
    PYTHONIOENCODING = "utf-8";
    SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
  };
} 