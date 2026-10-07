// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {HYQUBRegistry} from "../src/HYQUBRegistry.sol";

contract HYQUBRegistryTest is Test {
    HYQUBRegistry registry;

    address alice = address(0xA11CE);
    address bob = address(0xB0B);

    bytes32 keyHash1 = keccak256("initial-key");
    bytes32 keyHash2 = keccak256("rotated-key");

    function setUp() public {
        registry = new HYQUBRegistry();
    }

    function testRegisterWallet() public {
        registry.registerWallet(alice, keyHash1);

        assertTrue(registry.isRegistered(alice));
        assertEq(registry.getKeyHash(alice), keyHash1);
        assertEq(registry.getKeyVersion(alice), 1);
    }

    function testRegisterWalletEmitsEvent() public {
        vm.expectEmit(true, false, false, true);

        emit HYQUBRegistry.WalletRegistered(
            alice,
            keyHash1
        );

        registry.registerWallet(alice, keyHash1);
    }

    function testRegisterTwiceReverts() public {
        registry.registerWallet(alice, keyHash1);

        vm.expectRevert("Already registered");
        registry.registerWallet(alice, keyHash2);
    }

    function testRotateKey() public {
        registry.registerWallet(alice, keyHash1);

        registry.rotateKey(alice, keyHash2);

        assertEq(registry.getKeyHash(alice), keyHash2);
        assertEq(registry.getKeyVersion(alice), 2);
    }

    function testRotateKeyEmitsEvent() public {
        registry.registerWallet(alice, keyHash1);

        vm.expectEmit(true, false, false, true);

        emit HYQUBRegistry.KeyRotated(
            alice,
            keyHash2,
            2
        );

        registry.rotateKey(alice, keyHash2);
    }

    function testRotateWithoutRegisterReverts() public {
        vm.expectRevert("Not registered");

        registry.rotateKey(alice, keyHash1);
    }

    function testIsRegisteredFalseByDefault() public view {
        assertFalse(registry.isRegistered(alice));
    }

    function testGetKeyHashRevertsIfNotRegistered() public {
        vm.expectRevert("Not registered");

        registry.getKeyHash(alice);
    }

    function testGetKeyVersionRevertsIfNotRegistered() public {
        vm.expectRevert("Not registered");

        registry.getKeyVersion(alice);
    }

    function testKeyVersionIncrementsOnMultipleRotations() public {
        registry.registerWallet(alice, keyHash1);

        assertEq(registry.getKeyVersion(alice), 1);

        registry.rotateKey(alice, keyHash2);

        assertEq(registry.getKeyVersion(alice), 2);

        bytes32 keyHash3 = keccak256("third-key");

        registry.rotateKey(alice, keyHash3);

        assertEq(registry.getKeyVersion(alice), 3);
        assertEq(registry.getKeyHash(alice), keyHash3);
    }

    function testDifferentWalletsHaveSeparateProfiles() public {
        registry.registerWallet(alice, keyHash1);
        registry.registerWallet(bob, keyHash2);

        assertTrue(registry.isRegistered(alice));
        assertTrue(registry.isRegistered(bob));

        assertEq(registry.getKeyHash(alice), keyHash1);
        assertEq(registry.getKeyHash(bob), keyHash2);

        assertEq(registry.getKeyVersion(alice), 1);
        assertEq(registry.getKeyVersion(bob), 1);
    }

    function testNonRegistrarCannotRegister() public {
        vm.prank(alice);

        vm.expectRevert("Not authorized");

        registry.registerWallet(bob, keyHash1);
    }

    function testNonRegistrarCannotRotate() public {
        registry.registerWallet(alice, keyHash1);

        vm.prank(bob);

        vm.expectRevert("Not authorized");

        registry.rotateKey(alice, keyHash2);
    }
}
