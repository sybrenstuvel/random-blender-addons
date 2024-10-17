//go:build mage

package main

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/pelletier/go-toml/v2"
)

// BlenderManifest is just enough of a model for blender_manifest.toml to read
// what this build tool needs.
type BlenderManifest struct {
	SchemaVersion int
	Version       string
	Name          string
}

func Info() {
	manifest := loadManifest()
	fmt.Printf("Name   : %s\n", manifest.Name)
	fmt.Printf("Version: %s\n", manifest.Version)
}

func loadManifest() BlenderManifest {
	docBytes, err := os.ReadFile("blender_manifest.toml")
	if err != nil {
		panic(fmt.Sprintf("cannot read blender manifest: %v", err))
	}

	var manifest BlenderManifest
	err = toml.Unmarshal(docBytes, &manifest)
	if err != nil {
		panic(fmt.Sprintf("cannot parse blender manifest: %v", err))
	}

	return manifest
}

func buildZipPath() string {
	manifest := loadManifest()
	zipName := fmt.Sprintf("you-are-autosave-v%s.zip", manifest.Version)
	zipPath := filepath.Join("dist", zipName)
	return zipPath
}
