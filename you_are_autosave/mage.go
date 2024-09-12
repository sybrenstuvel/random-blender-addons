//go:build mage

package main

import (
	"fmt"
	"os"

	"github.com/pelletier/go-toml/v2"
)

type BlenderManifest struct {
	SchemaVersion int
	Version       string
}

func Version() {
	docBytes, err := os.ReadFile("blender_manifest.toml")
	if err != nil {
		panic(fmt.Sprintf("cannot read blender manifest: %v", err))
	}

	var manifest BlenderManifest
	err = toml.Unmarshal(docBytes, &manifest)
	if err != nil {
		panic(fmt.Sprintf("cannot parse blender manifest: %v", err))
	}

	fmt.Println(manifest.Version)
}
