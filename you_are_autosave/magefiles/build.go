//go:build mage

package main

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/magefile/mage/sh"
)

func Validate() error {
	return sh.RunV("blender", "--command", "extension", "validate")
}

func Build() error {
	zipPath := buildZipPath()

	zipDir := filepath.Dir(zipPath)
	if err := os.MkdirAll(zipDir, 0o777); err != nil {
		return nil
	}

	fmt.Printf("Creating %s\n", zipPath)
	return sh.RunV("blender", "--command", "extension", "build",
		// "--source-dir", ".",
		"--output-filepath", zipPath,
	)
}
