{pkgs}: {
  deps = [
    pkgs.glibcLocales
    pkgs.rustc
    pkgs.libiconv
    pkgs.cargo
    pkgs.bash
    pkgs.postgresql
    pkgs.openssl
  ];
}
